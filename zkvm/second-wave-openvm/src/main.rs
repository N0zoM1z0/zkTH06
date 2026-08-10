#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![cfg_attr(not(target_os = "zkvm"), allow(clippy::needless_borrows_for_generic_args))]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_first_item::ActiveItem;
use zkth06_player_bullet_lifecycle::{ActiveBullet, Vec3Bits};
use zkth06_player_bullets::BULLET_STATE_COLLIDED;
use zkth06_second_wave::{
    derive_second_wave_anchor, step_second_wave, SecondWaveEnemy, SecondWaveState,
    PROFILE_LAST_GAME_FRAME,
};

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKSWI1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 24;
const INPUT_FRAMES: usize = PROFILE_LAST_GAME_FRAME as usize;
const INCREMENTAL_TRANSITIONS: usize = 101;
const PROFILE_FLAGS: u8 = 15;
const STATE_DOMAIN: &[u8] = b"zkTH06/second-wave/projection/v1\0";
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/second-wave/v1\0";

struct Reader<'a> { bytes: &'a [u8], offset: usize }
impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self { Self { bytes, offset: 0 } }
    fn take(&mut self, count: usize) -> &'a [u8] {
        let end = self.offset.checked_add(count).unwrap_or_else(|| panic!());
        let value = self.bytes.get(self.offset..end).unwrap_or_else(|| panic!());
        self.offset = end;
        value
    }
    fn u8(&mut self) -> u8 { self.take(1)[0] }
    fn u16(&mut self) -> u16 { u16::from_le_bytes(self.take(2).try_into().unwrap_or_else(|_| panic!())) }
    fn u32(&mut self) -> u32 { u32::from_le_bytes(self.take(4).try_into().unwrap_or_else(|_| panic!())) }
}

fn u16d(d: &mut Sha256, value: u16) { d.update(&value.to_le_bytes()); }
fn i16d(d: &mut Sha256, value: i16) { d.update(&value.to_le_bytes()); }
fn u32d(d: &mut Sha256, value: u32) { d.update(&value.to_le_bytes()); }
fn i32d(d: &mut Sha256, value: i32) { d.update(&value.to_le_bytes()); }
fn vec3d(d: &mut Sha256, value: Vec3Bits) { u32d(d, value.x); u32d(d, value.y); u32d(d, value.z); }

fn enemy_digest(d: &mut Sha256, slot: u8, enemy: SecondWaveEnemy) {
    d.update(&[slot, u8::from(enemy.has_been_in_bounds)]);
    u16d(d, 0);
    i32d(d, enemy.ecl_timer.current);
    i32d(d, enemy.life);
    vec3d(d, enemy.position);
    u32d(d, enemy.axis_speed.x);
    u32d(d, enemy.axis_speed.y);
    u32d(d, enemy.angle_bits);
    u32d(d, enemy.angular_velocity_bits);
}

fn bullet_digest(d: &mut Sha256, slot: u8, state: u8, bullet: ActiveBullet) {
    d.update(&[slot, state]);
    u16d(d, 0);
    vec3d(d, bullet.position);
    vec3d(d, bullet.size);
    u32d(d, bullet.velocity.x);
    u32d(d, bullet.velocity.y);
    u32d(d, bullet.sideways_motion_bits);
    vec3d(d, bullet.unk_134);
    i32d(d, bullet.age.previous);
    i32d(d, bullet.age.current);
    i16d(d, bullet.damage);
    d.update(&[bullet.bullet_type, 0]);
    i16d(d, bullet.unk_152);
    i16d(d, bullet.spawn_position_idx);
    vec3d(d, bullet.sprite_position);
    i32d(d, bullet.sprite_timer.previous);
    i32d(d, bullet.sprite_timer.current);
    u32d(d, bullet.sprite_flags);
    u16d(d, bullet.sprite_active_index);
    u16d(d, bullet.sprite_anm_file_index);
    u32d(d, bullet.sprite_width_bits);
    u32d(d, bullet.sprite_height_bits);
}

fn item_digest(d: &mut Sha256, slot: u8, item: ActiveItem) {
    d.update(&[slot, item.item_type]);
    u16d(d, 0);
    vec3d(d, item.current_position);
    vec3d(d, item.start_position);
    vec3d(d, item.target_position);
    i32d(d, item.timer.previous);
    i32d(d, item.timer.current);
    d.update(&[item.state, item.unk_142, 1, 0]);
}

fn counts(state: &SecondWaveState) -> (u8, u8, u8, u8) {
    (
        state.enemies.iter().flatten().count() as u8,
        state.items.iter().flatten().count() as u8,
        state.first_item.wave.player.bullets.slots.iter().flatten().count() as u8,
        state.first_item.wave.bullet_states.iter().filter(|&&value| value == BULLET_STATE_COLLIDED).count() as u8,
    )
}

fn state_digest(d: &mut Sha256, state: &SecondWaveState) {
    let (enemy_count, item_count, bullet_count, collided_count) = counts(state);
    let frame = state.first_item.wave.player.shooting.enclosing.game_frame;
    u32d(d, frame);
    u32d(d, state.first_item.wave.score);
    vec3d(d, state.first_item.wave.last_enemy_hit);
    u16d(d, state.rng.seed);
    u32d(d, state.rng.generation);
    d.update(&[state.first_item.random_item_spawn_index, state.first_item.random_item_table_index]);
    u16d(d, state.first_item.item_next_index);
    u16d(d, state.first_item.item_count);
    i32d(d, state.first_item.subrank);
    u16d(d, state.first_item.current_power);
    d.update(&[enemy_count, item_count, bullet_count, collided_count]);
    u16d(d, state.enemy_bullets.next_index);
    u16d(d, state.enemy_bullets.bullet_count);
    i32d(d, state.enemy_bullets.timer.previous);
    i32d(d, state.enemy_bullets.timer.current);
    u16d(d, state.enemy_bullets.active_count);
    for (slot, enemy) in state.enemies.iter().copied().enumerate() {
        if let Some(enemy) = enemy { enemy_digest(d, slot as u8, enemy); }
    }
    for (slot, bullet) in state.first_item.wave.player.bullets.slots.iter().copied().enumerate() {
        if let Some(bullet) = bullet {
            bullet_digest(d, slot as u8, state.first_item.wave.bullet_states[slot], bullet);
        }
    }
    for (slot, item) in state.items.iter().copied().enumerate() {
        if let Some(item) = item { item_digest(d, slot as u8, item); }
    }
}

#[allow(clippy::needless_borrows_for_generic_args)]
pub fn main() {
    let input = read_vec();
    let mut reader = Reader::new(&input);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), SCHEMA_VERSION);
    assert_eq!(reader.u32() as usize, INPUT_FRAMES);
    assert_eq!(reader.u32() as usize, INCREMENTAL_TRANSITIONS);
    assert_eq!(reader.u8(), 0);
    assert_eq!(reader.u8(), 0);
    assert_eq!(reader.u8(), PROFILE_FLAGS);
    assert_eq!(reader.u8(), 0);
    assert_eq!(input.len(), HEADER_BYTES + INPUT_FRAMES * 2);
    let mut inputs = [0_u16; INPUT_FRAMES];
    for value in &mut inputs { *value = reader.u16(); }
    assert_eq!(reader.offset, input.len());

    let mut state = derive_second_wave_anchor(&inputs).unwrap_or_else(|_| panic!());
    let mut projection = Sha256::new();
    projection.update(STATE_DOMAIN);
    let mut maximum_enemies = 0_u32;
    let mut maximum_items = 0_u32;
    for game_frame in 250..=PROFILE_LAST_GAME_FRAME {
        state = step_second_wave(state, inputs[game_frame as usize - 1]).unwrap_or_else(|_| panic!());
        let current = counts(&state);
        maximum_enemies = maximum_enemies.max(u32::from(current.0));
        maximum_items = maximum_items.max(u32::from(current.1));
        state_digest(&mut projection, &state);
    }
    let projection_digest = projection.finalize();
    let final_counts = counts(&state);
    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    u32d(&mut statement, state.first_item.wave.player.shooting.enclosing.game_frame);
    u32d(&mut statement, INPUT_FRAMES as u32);
    u32d(&mut statement, INCREMENTAL_TRANSITIONS as u32);
    u32d(&mut statement, state.first_item.wave.score);
    u16d(&mut statement, state.rng.seed);
    u32d(&mut statement, state.rng.generation);
    statement.update(&[state.first_item.random_item_spawn_index, state.first_item.random_item_table_index]);
    u16d(&mut statement, state.first_item.item_next_index);
    u16d(&mut statement, state.first_item.item_count);
    i32d(&mut statement, state.first_item.subrank);
    u16d(&mut statement, state.first_item.current_power);
    statement.update(&[final_counts.0, final_counts.1, final_counts.2, final_counts.3]);
    u16d(&mut statement, state.enemy_bullets.next_index);
    u16d(&mut statement, state.enemy_bullets.bullet_count);
    i32d(&mut statement, state.enemy_bullets.timer.current);
    u16d(&mut statement, state.enemy_bullets.active_count);
    u32d(&mut statement, maximum_enemies);
    u32d(&mut statement, maximum_items);
    statement.update(&projection_digest);
    let digest = statement.finalize();
    for (index, word) in digest.chunks_exact(4).enumerate() {
        reveal_u32(u32::from_le_bytes(word.try_into().unwrap_or_else(|_| panic!())), index);
    }
}

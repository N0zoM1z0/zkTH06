#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![cfg_attr(
    not(target_os = "zkvm"),
    allow(clippy::needless_borrows_for_generic_args)
)]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_early_gameplay::{
    player_bullet_state, retail_early_gameplay_anchor, step_early_gameplay, EarlyEnemy,
    EarlyGameplayState,
};
use zkth06_first_item::{
    from_first_collision, step_first_item, ActiveItem, FirstItemState, PROFILE_LAST_GAME_FRAME,
};
use zkth06_player_bullet_lifecycle::{ActiveBullet, Vec3Bits};
use zkth06_player_bullets::BULLET_STATE_COLLIDED;

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKFII1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 24;
const RECORD_BYTES: usize = 2;
const MAX_TRANSITIONS: usize = (PROFILE_LAST_GAME_FRAME - 1) as usize;
const PROFILE_FLAGS: u8 = 7;
const STATE_DOMAIN: &[u8] = b"zkTH06/first-item/projection/v1\0";
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/first-item/v1\0";

struct Reader<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn take(&mut self, count: usize) -> &'a [u8] {
        let end = self.offset.checked_add(count).unwrap_or_else(|| panic!());
        let result = self.bytes.get(self.offset..end).unwrap_or_else(|| panic!());
        self.offset = end;
        result
    }

    fn u8(&mut self) -> u8 {
        self.take(1)[0]
    }

    fn u16(&mut self) -> u16 {
        u16::from_le_bytes(self.take(2).try_into().unwrap_or_else(|_| panic!()))
    }

    fn u32(&mut self) -> u32 {
        u32::from_le_bytes(self.take(4).try_into().unwrap_or_else(|_| panic!()))
    }
}

fn update_u16(digest: &mut Sha256, value: u16) {
    digest.update(&value.to_le_bytes());
}

fn update_i16(digest: &mut Sha256, value: i16) {
    digest.update(&value.to_le_bytes());
}

fn update_u32(digest: &mut Sha256, value: u32) {
    digest.update(&value.to_le_bytes());
}

fn update_i32(digest: &mut Sha256, value: i32) {
    digest.update(&value.to_le_bytes());
}

fn update_vec3(digest: &mut Sha256, value: Vec3Bits) {
    update_u32(digest, value.x);
    update_u32(digest, value.y);
    update_u32(digest, value.z);
}

fn update_enemy(digest: &mut Sha256, slot: u8, enemy: EarlyEnemy) {
    digest.update(&[slot, u8::from(enemy.has_been_in_bounds)]);
    update_u16(digest, 0);
    update_i32(digest, enemy.ecl_time);
    update_i32(digest, enemy.life);
    update_vec3(digest, enemy.position);
    update_u32(digest, enemy.axis_speed.x);
    update_u32(digest, enemy.axis_speed.y);
    update_u32(digest, enemy.angle_bits);
    update_u32(digest, enemy.angular_velocity_bits);
}

fn update_bullet(digest: &mut Sha256, slot: u8, state: u8, bullet: ActiveBullet) {
    digest.update(&[slot, state]);
    update_u16(digest, 0);
    update_vec3(digest, bullet.position);
    update_vec3(digest, bullet.size);
    update_u32(digest, bullet.velocity.x);
    update_u32(digest, bullet.velocity.y);
    update_u32(digest, bullet.sideways_motion_bits);
    update_vec3(digest, bullet.unk_134);
    update_i32(digest, bullet.age.previous);
    update_i32(digest, bullet.age.current);
    update_i16(digest, bullet.damage);
    digest.update(&[bullet.bullet_type, 0]);
    update_i16(digest, bullet.unk_152);
    update_i16(digest, bullet.spawn_position_idx);
    update_vec3(digest, bullet.sprite_position);
    update_i32(digest, bullet.sprite_timer.previous);
    update_i32(digest, bullet.sprite_timer.current);
    update_u32(digest, bullet.sprite_flags);
    update_u16(digest, bullet.sprite_active_index);
    update_u16(digest, bullet.sprite_anm_file_index);
    update_u32(digest, bullet.sprite_width_bits);
    update_u32(digest, bullet.sprite_height_bits);
}

fn update_item(digest: &mut Sha256, slot: u8, item: ActiveItem) {
    digest.update(&[slot, item.item_type]);
    update_u16(digest, 0);
    update_vec3(digest, item.current_position);
    update_vec3(digest, item.start_position);
    update_vec3(digest, item.target_position);
    update_i32(digest, item.timer.previous);
    update_i32(digest, item.timer.current);
    digest.update(&[item.state, item.unk_142, 1, 0]);
}

fn early_counts(state: &EarlyGameplayState) -> (u32, u32, u32) {
    (
        state.enemies.iter().flatten().count() as u32,
        state.player.bullets.slots.iter().flatten().count() as u32,
        u32::from(state.collided_slot.is_some()),
    )
}

fn item_counts(state: &FirstItemState) -> (u32, u32, u32, u32) {
    (
        state.wave.enemies.iter().flatten().count() as u32,
        state.wave.player.bullets.slots.iter().flatten().count() as u32,
        state
            .wave
            .bullet_states
            .iter()
            .filter(|&&value| value == BULLET_STATE_COLLIDED)
            .count() as u32,
        u32::from(state.item.is_some()),
    )
}

#[allow(clippy::too_many_arguments)]
fn update_prefix(
    digest: &mut Sha256,
    game_frame: u32,
    score: u32,
    target: Vec3Bits,
    enemy_count: u32,
    bullet_count: u32,
    collision_count: u32,
    active_item_count: u32,
    current_power: u16,
    subrank: i32,
    item_next_index: u16,
    random_spawn_index: u8,
    random_table_index: u8,
    item_count: u8,
) {
    update_u32(digest, game_frame);
    update_u32(digest, score);
    update_vec3(digest, target);
    digest.update(&[
        enemy_count as u8,
        bullet_count as u8,
        collision_count as u8,
        active_item_count as u8,
    ]);
    update_u16(digest, current_power);
    update_i32(digest, subrank);
    update_u16(digest, item_next_index);
    digest.update(&[random_spawn_index, random_table_index, item_count, 0]);
}

fn update_early_state(digest: &mut Sha256, state: &EarlyGameplayState) {
    let (enemy_count, bullet_count, collision_count) = early_counts(state);
    update_prefix(
        digest,
        state.player.shooting.enclosing.game_frame,
        state.score,
        state.last_enemy_hit,
        enemy_count,
        bullet_count,
        collision_count,
        0,
        0,
        0,
        0,
        1,
        0,
        0,
    );
    for (slot, enemy) in state.enemies.iter().copied().enumerate() {
        if let Some(enemy) = enemy {
            update_enemy(digest, slot as u8, enemy);
        }
    }
    for (slot, bullet) in state.player.bullets.slots.iter().copied().enumerate() {
        if let Some(bullet) = bullet {
            update_bullet(digest, slot as u8, player_bullet_state(state, slot), bullet);
        }
    }
}

fn update_item_state(digest: &mut Sha256, state: &FirstItemState) {
    let (enemy_count, bullet_count, collision_count, active_item_count) = item_counts(state);
    update_prefix(
        digest,
        state.wave.player.shooting.enclosing.game_frame,
        state.wave.score,
        state.wave.last_enemy_hit,
        enemy_count,
        bullet_count,
        collision_count,
        active_item_count,
        state.current_power,
        state.subrank,
        state.item_next_index,
        state.random_item_spawn_index,
        state.random_item_table_index,
        state.item_count as u8,
    );
    for (slot, enemy) in state.wave.enemies.iter().copied().enumerate() {
        if let Some(enemy) = enemy {
            update_enemy(digest, slot as u8, enemy);
        }
    }
    for (slot, bullet) in state.wave.player.bullets.slots.iter().copied().enumerate() {
        if let Some(bullet) = bullet {
            update_bullet(digest, slot as u8, state.wave.bullet_states[slot], bullet);
        }
    }
    if let Some(item) = state.item {
        update_item(digest, 0, item);
    }
}

#[allow(clippy::needless_borrows_for_generic_args)]
pub fn main() {
    let input = read_vec();
    let mut reader = Reader::new(&input);
    assert_eq!(reader.take(MAGIC.len()), MAGIC);
    assert_eq!(reader.u32(), SCHEMA_VERSION);
    let transition_count = reader.u32() as usize;
    assert!((1..=MAX_TRANSITIONS).contains(&transition_count));
    assert_eq!(reader.u8(), 0);
    assert_eq!(reader.u8(), 0);
    assert_eq!(reader.u8(), PROFILE_FLAGS);
    assert_eq!(reader.u8(), 0);
    assert_eq!(reader.u32(), 1);
    assert_eq!(input.len(), HEADER_BYTES + transition_count * RECORD_BYTES);

    let mut early = Some(retail_early_gameplay_anchor().unwrap_or_else(|_| panic!()));
    let mut item_state: Option<FirstItemState> = None;
    let mut state_digest = Sha256::new();
    state_digest.update(STATE_DOMAIN);
    update_early_state(
        &mut state_digest,
        early.as_ref().unwrap_or_else(|| panic!()),
    );
    let mut maximum_enemies = 0_u32;

    for _ in 0..transition_count {
        let input_mask = reader.u16();
        if let Some(prior) = early.take() {
            let next = step_early_gameplay(prior, input_mask).unwrap_or_else(|_| panic!());
            let counts = early_counts(&next);
            maximum_enemies = maximum_enemies.max(counts.0);
            if next.player.shooting.enclosing.game_frame == 208 {
                let next = from_first_collision(next).unwrap_or_else(|_| panic!());
                update_item_state(&mut state_digest, &next);
                item_state = Some(next);
            } else {
                update_early_state(&mut state_digest, &next);
                early = Some(next);
            }
        } else {
            let prior = item_state.take().unwrap_or_else(|| panic!());
            let next = step_first_item(prior, input_mask).unwrap_or_else(|_| panic!());
            maximum_enemies = maximum_enemies.max(item_counts(&next).0);
            update_item_state(&mut state_digest, &next);
            item_state = Some(next);
        }
    }
    assert_eq!(reader.offset, input.len());

    let (
        final_frame,
        score,
        current_power,
        subrank,
        random_spawn_index,
        random_table_index,
        item_count,
        active_item_count,
        collision_count,
        bullet_count,
        enemy_count,
    ) = if let Some(state) = item_state.as_ref() {
        let counts = item_counts(state);
        (
            state.wave.player.shooting.enclosing.game_frame,
            state.wave.score,
            state.current_power,
            state.subrank,
            u32::from(state.random_item_spawn_index),
            u32::from(state.random_item_table_index),
            u32::from(state.item_count),
            counts.3,
            counts.2,
            counts.1,
            counts.0,
        )
    } else {
        let state = early.as_ref().unwrap_or_else(|| panic!());
        let counts = early_counts(state);
        (
            state.player.shooting.enclosing.game_frame,
            state.score,
            0,
            0,
            1,
            0,
            0,
            0,
            counts.2,
            counts.1,
            counts.0,
        )
    };
    let projection_digest = state_digest.finalize();
    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    statement.update(&final_frame.to_le_bytes());
    statement.update(&(transition_count as u32).to_le_bytes());
    statement.update(&score.to_le_bytes());
    statement.update(&u32::from(current_power).to_le_bytes());
    statement.update(&subrank.to_le_bytes());
    statement.update(&random_spawn_index.to_le_bytes());
    statement.update(&random_table_index.to_le_bytes());
    statement.update(&item_count.to_le_bytes());
    statement.update(&active_item_count.to_le_bytes());
    statement.update(&collision_count.to_le_bytes());
    statement.update(&bullet_count.to_le_bytes());
    statement.update(&enemy_count.to_le_bytes());
    statement.update(&maximum_enemies.to_le_bytes());
    statement.update(&projection_digest);
    let digest = statement.finalize();
    for (index, word) in digest.chunks_exact(4).enumerate() {
        reveal_u32(
            u32::from_le_bytes(word.try_into().unwrap_or_else(|_| panic!())),
            index,
        );
    }
}

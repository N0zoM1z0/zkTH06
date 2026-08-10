#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_early_gameplay::{
    player_bullet_state, retail_early_gameplay_anchor, step_early_gameplay, EarlyEnemy,
    EarlyGameplayState,
};
use zkth06_first_wave::{
    from_first_collision, step_first_wave, FirstWaveState, ANCHOR_GAME_FRAME,
    PROFILE_LAST_GAME_FRAME,
};
use zkth06_player_bullet_lifecycle::{ActiveBullet, Vec3Bits};
use zkth06_player_bullets::BULLET_STATE_COLLIDED;

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKFWI1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 24;
const RECORD_BYTES: usize = 2;
const MAX_TRANSITIONS: usize = (PROFILE_LAST_GAME_FRAME - 1) as usize;
const PROFILE_FLAGS: u8 = 3;
const STATE_DOMAIN: &[u8] = b"zkTH06/first-wave/projection/v1\0";
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/first-wave/v1\0";

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

fn early_counts(state: &EarlyGameplayState) -> (u32, u32, u32) {
    (
        state.enemies.iter().flatten().count() as u32,
        state.player.bullets.slots.iter().flatten().count() as u32,
        u32::from(state.collided_slot.is_some()),
    )
}

fn wave_counts(state: &FirstWaveState) -> (u32, u32, u32) {
    (
        state.enemies.iter().flatten().count() as u32,
        state.player.bullets.slots.iter().flatten().count() as u32,
        state
            .bullet_states
            .iter()
            .filter(|&&value| value == BULLET_STATE_COLLIDED)
            .count() as u32,
    )
}

fn update_prefix(
    digest: &mut Sha256,
    game_frame: u32,
    score: u32,
    target: Vec3Bits,
    enemy_count: u32,
    bullet_count: u32,
    collision_count: u32,
) {
    update_u32(digest, game_frame);
    update_u32(digest, score);
    update_vec3(digest, target);
    digest.update(&[
        enemy_count as u8,
        bullet_count as u8,
        collision_count as u8,
        0,
    ]);
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

fn update_wave_state(digest: &mut Sha256, state: &FirstWaveState) {
    let (enemy_count, bullet_count, collision_count) = wave_counts(state);
    update_prefix(
        digest,
        state.player.shooting.enclosing.game_frame,
        state.score,
        state.last_enemy_hit,
        enemy_count,
        bullet_count,
        collision_count,
    );
    for (slot, enemy) in state.enemies.iter().copied().enumerate() {
        if let Some(enemy) = enemy {
            update_enemy(digest, slot as u8, enemy);
        }
    }
    for (slot, bullet) in state.player.bullets.slots.iter().copied().enumerate() {
        if let Some(bullet) = bullet {
            update_bullet(digest, slot as u8, state.bullet_states[slot], bullet);
        }
    }
}

fn early_in_bounds_enemies(state: &EarlyGameplayState) -> u32 {
    state
        .enemies
        .iter()
        .flatten()
        .filter(|enemy| enemy.has_been_in_bounds)
        .count() as u32
}

fn wave_in_bounds_enemies(state: &FirstWaveState) -> u32 {
    state
        .enemies
        .iter()
        .flatten()
        .filter(|enemy| enemy.has_been_in_bounds)
        .count() as u32
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
    let mut wave: Option<FirstWaveState> = None;
    let mut state_digest = Sha256::new();
    state_digest.update(STATE_DOMAIN);
    update_early_state(&mut state_digest, early.as_ref().unwrap_or_else(|| panic!()));
    let mut damage_calls = 0_u32;
    let mut collision_events = 0_u32;
    let mut maximum_enemies = 0_u32;

    for _ in 0..transition_count {
        let input_mask = reader.u16();
        if let Some(prior) = early.take() {
            if prior.player.shooting.enclosing.game_frame < ANCHOR_GAME_FRAME {
                let prior_collisions = early_counts(&prior).2;
                let next = step_early_gameplay(prior, input_mask).unwrap_or_else(|_| panic!());
                let counts = early_counts(&next);
                let new_collisions = counts.2.checked_sub(prior_collisions).unwrap_or_else(|| panic!());
                collision_events = collision_events.checked_add(new_collisions).unwrap_or_else(|| panic!());
                damage_calls = damage_calls
                    .checked_add(early_in_bounds_enemies(&next))
                    .and_then(|value| value.checked_add(new_collisions))
                    .unwrap_or_else(|| panic!());
                maximum_enemies = maximum_enemies.max(counts.0);
                update_early_state(&mut state_digest, &next);
                early = Some(next);
            } else {
                let prior = from_first_collision(prior).unwrap_or_else(|_| panic!());
                let prior_collisions = wave_counts(&prior).2;
                let next = step_first_wave(prior, input_mask).unwrap_or_else(|_| panic!());
                let counts = wave_counts(&next);
                let new_collisions = counts.2.checked_sub(prior_collisions).unwrap_or_else(|| panic!());
                collision_events = collision_events.checked_add(new_collisions).unwrap_or_else(|| panic!());
                damage_calls = damage_calls
                    .checked_add(wave_in_bounds_enemies(&next))
                    .and_then(|value| value.checked_add(new_collisions))
                    .unwrap_or_else(|| panic!());
                maximum_enemies = maximum_enemies.max(counts.0);
                update_wave_state(&mut state_digest, &next);
                wave = Some(next);
            }
        } else {
            let prior = wave.take().unwrap_or_else(|| panic!());
            let prior_collisions = wave_counts(&prior).2;
            let next = step_first_wave(prior, input_mask).unwrap_or_else(|_| panic!());
            let counts = wave_counts(&next);
            let new_collisions = counts.2.checked_sub(prior_collisions).unwrap_or_else(|| panic!());
            collision_events = collision_events.checked_add(new_collisions).unwrap_or_else(|| panic!());
            damage_calls = damage_calls
                .checked_add(wave_in_bounds_enemies(&next))
                .and_then(|value| value.checked_add(new_collisions))
                .unwrap_or_else(|| panic!());
            maximum_enemies = maximum_enemies.max(counts.0);
            update_wave_state(&mut state_digest, &next);
            wave = Some(next);
        }
    }
    assert_eq!(reader.offset, input.len());

    let (final_frame, score, enemy_count, bullet_count, collision_count) = if let Some(state) = wave.as_ref() {
        let counts = wave_counts(state);
        (
            state.player.shooting.enclosing.game_frame,
            state.score,
            counts.0,
            counts.1,
            counts.2,
        )
    } else {
        let state = early.as_ref().unwrap_or_else(|| panic!());
        let counts = early_counts(state);
        (
            state.player.shooting.enclosing.game_frame,
            state.score,
            counts.0,
            counts.1,
            counts.2,
        )
    };
    let projection_digest = state_digest.finalize();
    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    statement.update(&final_frame.to_le_bytes());
    statement.update(&(transition_count as u32).to_le_bytes());
    statement.update(&score.to_le_bytes());
    statement.update(&damage_calls.to_le_bytes());
    statement.update(&collision_events.to_le_bytes());
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

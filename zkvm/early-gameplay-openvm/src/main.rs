#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_early_gameplay::{
    retail_early_gameplay_anchor, step_early_gameplay, EarlyEnemy, EarlyGameplayState,
    PROFILE_LAST_GAME_FRAME,
};
use zkth06_player_bullet_lifecycle::Vec3Bits;

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKEGI1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 24;
const RECORD_BYTES: usize = 2;
const MAX_TRANSITIONS: usize = (PROFILE_LAST_GAME_FRAME - 1) as usize;
const PROFILE_FLAGS: u8 = 1;
const NO_COLLISION: u32 = u32::MAX;
const STATE_DOMAIN: &[u8] = b"zkTH06/early-gameplay/projection/v1\0";
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/early-gameplay/v1\0";

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
        let value = self.bytes.get(self.offset..end).unwrap_or_else(|| panic!());
        self.offset = end;
        value
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

fn enemy_count(state: &EarlyGameplayState) -> u32 {
    state.enemies.iter().flatten().count() as u32
}

fn in_bounds_enemy_count(state: &EarlyGameplayState) -> u32 {
    state
        .enemies
        .iter()
        .flatten()
        .filter(|enemy| enemy.has_been_in_bounds)
        .count() as u32
}

fn update_state(digest: &mut Sha256, state: &EarlyGameplayState) {
    update_u32(digest, state.player.shooting.enclosing.game_frame);
    update_u32(digest, state.score);
    update_vec3(digest, state.last_enemy_hit);
    digest.update(&[state.collided_slot.unwrap_or(0xff)]);
    digest.update(&[enemy_count(state) as u8]);
    for (slot, enemy) in state.enemies.iter().copied().enumerate() {
        if let Some(enemy) = enemy {
            update_enemy(digest, slot as u8, enemy);
        }
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
    assert_eq!(reader.u8(), 0); // Reimu
    assert_eq!(reader.u8(), 0); // shot type A
    assert_eq!(reader.u8(), PROFILE_FLAGS);
    assert_eq!(reader.u8(), 0); // reserved
    assert_eq!(reader.u32(), 1); // fixed gameplay-frame anchor
    let expected_len = HEADER_BYTES
        .checked_add(
            transition_count
                .checked_mul(RECORD_BYTES)
                .unwrap_or_else(|| panic!()),
        )
        .unwrap_or_else(|| panic!());
    assert_eq!(input.len(), expected_len);

    let mut state = retail_early_gameplay_anchor().unwrap_or_else(|_| panic!());
    let mut state_digest = Sha256::new();
    state_digest.update(STATE_DOMAIN);
    update_state(&mut state_digest, &state);
    let mut damage_calls = 0_u32;
    let mut collision_events = 0_u32;
    let mut maximum_enemies = 0_u32;
    for _ in 0..transition_count {
        let prior_collision = state.collided_slot;
        state = step_early_gameplay(state, reader.u16()).unwrap_or_else(|_| panic!());
        let collision_this_frame =
            u32::from(prior_collision.is_none() && state.collided_slot.is_some());
        collision_events = collision_events
            .checked_add(collision_this_frame)
            .unwrap_or_else(|| panic!());
        damage_calls = damage_calls
            .checked_add(in_bounds_enemy_count(&state))
            .and_then(|value| value.checked_add(collision_this_frame))
            .unwrap_or_else(|| panic!());
        maximum_enemies = maximum_enemies.max(enemy_count(&state));
        update_state(&mut state_digest, &state);
    }
    assert_eq!(reader.offset, input.len());
    let projection_digest = state_digest.finalize();
    let collided_slot = state.collided_slot.map_or(NO_COLLISION, u32::from);

    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    statement.update(&state.player.shooting.enclosing.game_frame.to_le_bytes());
    statement.update(&(transition_count as u32).to_le_bytes());
    statement.update(&state.score.to_le_bytes());
    statement.update(&damage_calls.to_le_bytes());
    statement.update(&collision_events.to_le_bytes());
    statement.update(&collided_slot.to_le_bytes());
    statement.update(&enemy_count(&state).to_le_bytes());
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

#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_player_bullet_lifecycle::{
    reimu_a, retail_lifecycle_anchor_state, step_player_bullet_lifecycle, ActiveBullet,
    PlayerBulletLifecycleState, Vec2Bits, Vec3Bits, PROFILE_LAST_GAME_FRAME,
};

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKPLI1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 24;
const RECORD_BYTES: usize = 2;
const MAX_TRANSITIONS: usize = (PROFILE_LAST_GAME_FRAME - 1) as usize;
const PROFILE_FLAGS: u8 = 1;
const STATE_DOMAIN: &[u8] = b"zkTH06/player-bullet-lifecycle/state/v1\0";
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/player-bullet-lifecycle/v1\0";

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

fn update_i16(digest: &mut Sha256, value: i16) {
    digest.update(&value.to_le_bytes());
}

fn update_u32(digest: &mut Sha256, value: u32) {
    digest.update(&value.to_le_bytes());
}

fn update_i32(digest: &mut Sha256, value: i32) {
    digest.update(&value.to_le_bytes());
}

fn update_vec2(digest: &mut Sha256, value: Vec2Bits) {
    update_u32(digest, value.x);
    update_u32(digest, value.y);
}

fn update_vec3(digest: &mut Sha256, value: Vec3Bits) {
    update_u32(digest, value.x);
    update_u32(digest, value.y);
    update_u32(digest, value.z);
}

fn update_bullet(digest: &mut Sha256, slot: u8, bullet: ActiveBullet) {
    digest.update(&[slot, bullet.bullet_type]);
    update_i16(digest, bullet.damage);
    update_i16(digest, bullet.unk_152);
    update_i16(digest, bullet.spawn_position_idx);
    update_vec3(digest, bullet.position);
    update_vec3(digest, bullet.size);
    update_vec2(digest, bullet.velocity);
    update_u32(digest, bullet.sideways_motion_bits);
    update_vec3(digest, bullet.unk_134);
    update_i32(digest, bullet.age.previous);
    update_u32(digest, 0); // fixed full-speed age subframe
    update_i32(digest, bullet.age.current);
    update_vec3(digest, bullet.sprite_position);
    update_i32(digest, bullet.sprite_timer.previous);
    update_i32(digest, bullet.sprite_timer.current);
    update_u32(digest, bullet.sprite_flags);
    update_u16(digest, bullet.sprite_active_index);
    update_u16(digest, bullet.sprite_anm_file_index);
    update_u32(digest, bullet.sprite_width_bits);
    update_u32(digest, bullet.sprite_height_bits);
}

fn active_count(state: &PlayerBulletLifecycleState) -> u32 {
    state.bullets.slots.iter().flatten().count() as u32
}

fn update_state(digest: &mut Sha256, state: &PlayerBulletLifecycleState) {
    let shooting = &state.shooting;
    update_u32(digest, shooting.enclosing.game_frame);
    digest.update(&[shooting.enclosing.life_state.retail_value()]);
    digest.update(&[u8::from(shooting.enclosing.is_time_stopped)
        | (u8::from(shooting.enclosing.bomb_active) << 1)
        | (u8::from(shooting.is_focus) << 2)]);
    update_i32(digest, shooting.enclosing.invulnerability_timer);
    update_u32(digest, shooting.enclosing.position.x_bits);
    update_u32(digest, shooting.enclosing.position.y_bits);
    update_u16(digest, shooting.previous_frame_input);
    update_i32(digest, shooting.fire_bullet_timer.previous);
    update_i32(digest, shooting.fire_bullet_timer.current);
    update_u32(digest, shooting.spawn_call_count);
    digest.update(&[active_count(state) as u8]);
    for (slot, bullet) in state.bullets.slots.iter().copied().enumerate() {
        if let Some(bullet) = bullet {
            update_bullet(digest, slot as u8, bullet);
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

    let config = reimu_a();
    let mut state = retail_lifecycle_anchor_state(config).unwrap_or_else(|_| panic!());
    let mut state_digest = Sha256::new();
    state_digest.update(STATE_DOMAIN);
    update_state(&mut state_digest, &state);
    let mut initialized = 0_u32;
    let mut reclaimed = 0_u32;
    let mut maximum_active = 0_u32;
    for _ in 0..transition_count {
        let previous_active = active_count(&state);
        state =
            step_player_bullet_lifecycle(config, state, reader.u16()).unwrap_or_else(|_| panic!());
        let next_active = active_count(&state);
        let new_bullets = state
            .bullets
            .slots
            .iter()
            .flatten()
            .filter(|bullet| bullet.age.current == 0)
            .count() as u32;
        initialized = initialized
            .checked_add(new_bullets)
            .unwrap_or_else(|| panic!());
        reclaimed = reclaimed
            .checked_add(
                previous_active
                    .checked_add(new_bullets)
                    .and_then(|value| value.checked_sub(next_active))
                    .unwrap_or_else(|| panic!()),
            )
            .unwrap_or_else(|| panic!());
        maximum_active = maximum_active.max(next_active);
        update_state(&mut state_digest, &state);
    }
    assert_eq!(reader.offset, input.len());
    let lifecycle_digest = state_digest.finalize();

    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    statement.update(&state.shooting.enclosing.game_frame.to_le_bytes());
    statement.update(&(transition_count as u32).to_le_bytes());
    statement.update(&state.shooting.spawn_call_count.to_le_bytes());
    statement.update(&initialized.to_le_bytes());
    statement.update(&reclaimed.to_le_bytes());
    statement.update(&active_count(&state).to_le_bytes());
    statement.update(&maximum_active.to_le_bytes());
    statement.update(&lifecycle_digest);
    let digest = statement.finalize();
    for (index, word) in digest.chunks_exact(4).enumerate() {
        reveal_u32(
            u32::from_le_bytes(word.try_into().unwrap_or_else(|_| panic!())),
            index,
        );
    }
}

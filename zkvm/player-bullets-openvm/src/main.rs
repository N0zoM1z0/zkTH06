#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_player_bullets::{
    spawn_reimu_a, InitializedBullet, SlotCarry, SpawnInput, Vec3Bits, PLAYER_BULLET_SLOTS,
};

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKPBI1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 20;
const RECORD_BYTES: usize = 124;
const MAX_CALLS: usize = 2_048;
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/player-bullets/v1\0";
const OUTPUT_DOMAIN: &[u8] = b"zkTH06/player-bullets/output/v1\0";

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

    fn vec3(&mut self) -> Vec3Bits {
        Vec3Bits {
            x: self.u32(),
            y: self.u32(),
            z: self.u32(),
        }
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

fn update_allocation(digest: &mut Sha256, bullet: InitializedBullet) {
    digest.update(&[
        bullet.slot,
        bullet.bullet_data_index,
        bullet.bullet_type,
        bullet.source_spawn_position_idx,
    ]);
    update_i16(digest, bullet.damage);
    update_u16(digest, bullet.requested_anm_script);
    update_vec3(digest, bullet.position);
    update_vec3(digest, bullet.size);
    update_u32(digest, bullet.velocity.x);
    update_u32(digest, bullet.velocity.y);
    update_u32(digest, bullet.sideways_motion_bits);
    update_vec3(digest, bullet.unk_134);
    update_i32(digest, bullet.timer_previous);
    update_u32(digest, bullet.timer_subframe_bits);
    update_i32(digest, bullet.timer_current);
    update_i16(digest, bullet.unk_152);
    update_i16(digest, bullet.stored_spawn_position_idx);
}

#[allow(clippy::needless_borrows_for_generic_args)]
pub fn main() {
    let input = read_vec();
    let mut reader = Reader::new(&input);
    assert_eq!(reader.take(MAGIC.len()), MAGIC);
    assert_eq!(reader.u32(), SCHEMA_VERSION);
    let call_count = reader.u32() as usize;
    assert!(call_count <= MAX_CALLS);
    assert_eq!(reader.u8(), 0); // Reimu
    assert_eq!(reader.u8(), 0); // shot type A
    assert_eq!(reader.u8(), 3); // maximum supported rank
    assert_eq!(reader.u8(), 1); // zero-carry finite-vector profile
    let expected_len = HEADER_BYTES
        .checked_add(call_count.checked_mul(RECORD_BYTES).unwrap_or_else(|| panic!()))
        .unwrap_or_else(|| panic!());
    assert_eq!(input.len(), expected_len);

    let mut output_digest = Sha256::new();
    output_digest.update(OUTPUT_DOMAIN);
    let mut initialized_bullets = 0_u32;
    let mut rank_calls = [0_u32; 3];
    let mut zero_allocation_calls = 0_u32;
    let mut maximum_active = 0_u32;
    let mut previous_game_frame = 0_u32;
    for _ in 0..call_count {
        let game_frame = reader.u32();
        assert!(game_frame > previous_game_frame);
        previous_game_frame = game_frame;
        let current_power = reader.u16();
        let timer = reader.u8();
        let _is_focus = reader.u8();
        let player_position = reader.vec3();
        let orb_positions = [reader.vec3(), reader.vec3()];
        let mut slot_states = [0_u8; PLAYER_BULLET_SLOTS];
        let mut active = 0_u32;
        for state in &mut slot_states {
            *state = reader.u8();
            active += u32::from(*state != 0);
        }
        maximum_active = maximum_active.max(active);
        let input_state = SpawnInput {
            timer,
            current_power,
            player_position,
            orb_positions,
            slot_states,
            slot_carry: [SlotCarry::default(); PLAYER_BULLET_SLOTS],
        };
        let output = spawn_reimu_a(input_state).unwrap_or_else(|_| panic!());
        initialized_bullets = initialized_bullets
            .checked_add(u32::from(output.allocation_count))
            .unwrap_or_else(|| panic!());
        zero_allocation_calls += u32::from(output.allocation_count == 0);
        rank_calls[if current_power < 8 {
            0
        } else if current_power < 16 {
            1
        } else {
            2
        }] += 1;
        update_u32(&mut output_digest, game_frame);
        output_digest.update(&[output.allocation_count]);
        for allocation in output
            .allocations
            .iter()
            .take(usize::from(output.allocation_count))
        {
            update_allocation(&mut output_digest, *allocation);
        }
    }
    assert_eq!(reader.offset, input.len());
    let geometry_digest = output_digest.finalize();

    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    statement.update(&previous_game_frame.to_le_bytes());
    statement.update(&(call_count as u32).to_le_bytes());
    statement.update(&initialized_bullets.to_le_bytes());
    for count in rank_calls {
        statement.update(&count.to_le_bytes());
    }
    statement.update(&zero_allocation_calls.to_le_bytes());
    statement.update(&maximum_active.to_le_bytes());
    statement.update(&[0, 0, 3, 1]);
    statement.update(&geometry_digest);
    let digest = statement.finalize();
    for (index, word) in digest.chunks_exact(4).enumerate() {
        reveal_u32(
            u32::from_le_bytes(word.try_into().unwrap_or_else(|_| panic!())),
            index,
        );
    }
}

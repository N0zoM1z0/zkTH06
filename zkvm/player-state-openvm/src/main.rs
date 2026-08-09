#![cfg_attr(target_os = "zkvm", no_main)]
#![cfg_attr(target_os = "zkvm", no_std)]
#![forbid(unsafe_code)]

use openvm::io::{read_vec, reveal_u32};
#[cfg(not(target_os = "zkvm"))]
use openvm_sha2::Digest;
use openvm_sha2::Sha256;
use zkth06_player_motion::enclosing::{
    retail_anchor_state, step_enclosing_player, PlayerConfig,
};

openvm::entry!(main);

const MAGIC: &[u8; 8] = b"ZKPSI1\0\0";
const SCHEMA_VERSION: u32 = 1;
const HEADER_BYTES: usize = 20;
const RECORD_BYTES: usize = 2;
const MAX_TRANSITIONS: usize = 4_096;
const STATEMENT_DOMAIN: &[u8] = b"zkTH06/openvm/player-state/v1\0";

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

// The zkVM SHA-256 inherent API requires slices, while its host stand-in uses
// the generic Digest trait and triggers this host-only Clippy suggestion.
#[allow(clippy::needless_borrows_for_generic_args)]
pub fn main() {
    let input = read_vec();
    let mut reader = Reader::new(&input);
    assert_eq!(reader.take(MAGIC.len()), MAGIC);
    assert_eq!(reader.u32(), SCHEMA_VERSION);
    let transition_count = reader.u32() as usize;
    assert!(transition_count <= MAX_TRANSITIONS);
    let config = PlayerConfig {
        character: reader.u8(),
        shot_type: reader.u8(),
    };
    assert_eq!(reader.u8(), 0); // closed-profile flags
    assert_eq!(reader.u8(), 0); // reserved
    let expected_len = HEADER_BYTES
        .checked_add(
            transition_count
                .checked_mul(RECORD_BYTES)
                .unwrap_or_else(|| panic!()),
        )
        .unwrap_or_else(|| panic!());
    assert_eq!(input.len(), expected_len);

    let mut state = retail_anchor_state(config).unwrap_or_else(|_| panic!());
    for _ in 0..transition_count {
        state = step_enclosing_player(config, state, reader.u16()).unwrap_or_else(|_| panic!());
    }
    assert_eq!(reader.offset, input.len());

    let mut statement = Sha256::new();
    statement.update(STATEMENT_DOMAIN);
    statement.update(&input);
    statement.update(&state.game_frame.to_le_bytes());
    statement.update(&state.position.x_bits.to_le_bytes());
    statement.update(&state.position.y_bits.to_le_bytes());
    statement.update(&[state.life_state.retail_value()]);
    statement.update(&[u8::from(state.is_time_stopped) | (u8::from(state.bomb_active) << 1)]);
    statement.update(&[0_u8; 2]);
    statement.update(&state.invulnerability_timer.to_le_bytes());
    let digest = statement.finalize();
    for (index, word) in digest.chunks_exact(4).enumerate() {
        reveal_u32(
            u32::from_le_bytes(word.try_into().unwrap_or_else(|_| panic!())),
            index,
        );
    }
}

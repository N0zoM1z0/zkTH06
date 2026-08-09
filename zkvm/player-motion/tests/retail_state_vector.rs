use zkth06_player_motion::enclosing::{
    retail_anchor_state, step_enclosing_player, EnclosingPlayerState, PlayerConfig,
    PlayerLifeState,
};
use zkth06_player_motion::Position;

const VECTOR: &[u8] = include_bytes!("../../../evidence/player-state-002677-2000-v1.bin");
const MAGIC: &[u8; 8] = b"ZKPSV1\0\0";
const HEADER_BYTES: usize = 160;
const RECORD_BYTES: usize = 20;

struct Reader<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn take(&mut self, count: usize) -> &'a [u8] {
        let end = self.offset.checked_add(count).expect("vector offset overflow");
        let value = self.bytes.get(self.offset..end).expect("truncated vector");
        self.offset = end;
        value
    }

    fn u8(&mut self) -> u8 {
        self.take(1)[0]
    }

    fn u16(&mut self) -> u16 {
        u16::from_le_bytes(self.take(2).try_into().unwrap())
    }

    fn u32(&mut self) -> u32 {
        u32::from_le_bytes(self.take(4).try_into().unwrap())
    }

    fn i32(&mut self) -> i32 {
        i32::from_le_bytes(self.take(4).try_into().unwrap())
    }
}

fn decode_hex(value: &str) -> Vec<u8> {
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text = core::str::from_utf8(pair).unwrap();
            u8::from_str_radix(text, 16).unwrap()
        })
        .collect()
}

fn read_expected_state(reader: &mut Reader<'_>) -> (u32, u16, EnclosingPlayerState) {
    let index = reader.u32();
    let input = reader.u16();
    let life_state = match reader.u8() {
        0 => PlayerLifeState::Alive,
        3 => PlayerLifeState::Invulnerable,
        value => panic!("unsupported fixture player state {value}"),
    };
    let flags = reader.u8();
    assert_eq!(flags & !3, 0);
    let invulnerability_timer = reader.i32();
    let position = Position {
        x_bits: reader.u32(),
        y_bits: reader.u32(),
    };
    (
        index,
        input,
        EnclosingPlayerState {
            game_frame: index + 1,
            position,
            life_state,
            invulnerability_timer,
            is_time_stopped: flags & 1 != 0,
            bomb_active: flags & 2 != 0,
        },
    )
}

#[test]
fn enclosing_state_matches_all_retail_transitions_without_environment_witnesses() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, RECORD_BYTES);
    let source_frames = reader.u32() as usize;
    assert_eq!(source_frames, 2_000);
    let config = PlayerConfig {
        character: reader.u8(),
        shot_type: reader.u8(),
    };
    assert_eq!(reader.u8(), 0, "unexpected profile flags");
    assert_eq!(reader.u8(), 0, "nonzero reserved byte");
    assert_eq!(reader.u32(), 1, "unexpected anchor game frame");
    assert_eq!(
        reader.take(32),
        decode_hex("9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245")
    );
    assert_eq!(
        reader.take(32),
        decode_hex("01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f")
    );
    assert!(reader.take(32).iter().any(|byte| *byte != 0));
    assert!(reader.take(32).iter().any(|byte| *byte != 0));
    assert_eq!(reader.offset, HEADER_BYTES);
    assert_eq!(VECTOR.len(), HEADER_BYTES + source_frames * RECORD_BYTES);

    let (initial_index, _, expected_initial) = read_expected_state(&mut reader);
    assert_eq!(initial_index, 0);
    let mut actual = retail_anchor_state(config).unwrap();
    assert_eq!(actual, expected_initial);

    for expected_index in 1..source_frames {
        let record_start = reader.offset;
        let (index, input, expected) = read_expected_state(&mut reader);
        assert_eq!(index as usize, expected_index);
        actual = step_enclosing_player(config, actual, input)
            .unwrap_or_else(|error| panic!("frame {} rejected: {error:?}", index + 1));
        assert_eq!(actual, expected, "enclosing-state mismatch at frame {}", index + 1);
        assert_eq!(reader.offset - record_start, RECORD_BYTES);
    }
    assert_eq!(reader.offset, VECTOR.len());
    assert_eq!(actual.game_frame, 2_000);
    assert_eq!(actual.life_state, PlayerLifeState::Alive);
    assert_eq!(actual.invulnerability_timer, 1_760);
    assert_eq!(actual.position.x_bits, 1_124_577_352);
    assert_eq!(actual.position.y_bits, 1_118_370_860);
}

use zkth06_player_motion::{step_position, MotionEnvironment, Position};

const VECTOR: &[u8] = include_bytes!("../../../evidence/player-motion-002677-2000-v1.bin");
const MAGIC: &[u8; 8] = b"ZKPMV1\0\0";
const HEADER_BYTES: usize = 120;
const RECORD_BYTES: usize = 68;

struct Reader<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn take(&mut self, count: usize) -> &'a [u8] {
        let end = self
            .offset
            .checked_add(count)
            .expect("vector offset overflow");
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
}

fn decode_hex(value: &str) -> Vec<u8> {
    assert_eq!(value.len() % 2, 0);
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text = core::str::from_utf8(pair).unwrap();
            u8::from_str_radix(text, 16).unwrap()
        })
        .collect()
}

#[test]
fn retail_player_positions_match_all_consecutive_transitions() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, RECORD_BYTES);
    let source_frames = reader.u32() as usize;
    assert_eq!(source_frames, 2_000);
    assert_eq!(
        reader.take(32),
        decode_hex("9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245")
    );
    assert_eq!(
        reader.take(32),
        decode_hex("01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f")
    );
    let retail_trace_hash = reader.take(32);
    assert!(retail_trace_hash.iter().any(|byte| *byte != 0));
    assert_eq!(reader.offset, HEADER_BYTES);

    let transition_count = source_frames - 1;
    assert_eq!(VECTOR.len(), HEADER_BYTES + transition_count * RECORD_BYTES);
    let mut prior_expected = None;
    for expected_index in 1..source_frames {
        let record_start = reader.offset;
        let index = reader.u32() as usize;
        assert_eq!(index, expected_index);
        let input = reader.u16();
        let player_state = reader.u8();
        let flags = reader.u8();
        assert_eq!(flags & !1, 0);
        let environment = MotionEnvironment {
            player_state,
            is_time_stopped: flags & 1 != 0,
            effective_rate_bits: reader.u32(),
            movement_min_x_bits: reader.u32(),
            movement_min_y_bits: reader.u32(),
            movement_size_x_bits: reader.u32(),
            movement_size_y_bits: reader.u32(),
            horizontal_multiplier_bits: reader.u32(),
            vertical_multiplier_bits: reader.u32(),
            orthogonal_speed_bits: reader.u32(),
            orthogonal_focus_speed_bits: reader.u32(),
            diagonal_speed_bits: reader.u32(),
            diagonal_focus_speed_bits: reader.u32(),
        };
        let previous = Position {
            x_bits: reader.u32(),
            y_bits: reader.u32(),
        };
        let expected = Position {
            x_bits: reader.u32(),
            y_bits: reader.u32(),
        };
        if let Some(prior) = prior_expected {
            assert_eq!(previous, prior, "discontinuous fixture at frame {index}");
        }
        let actual = step_position(previous, input, environment)
            .unwrap_or_else(|error| panic!("frame {index} rejected: {error:?}"));
        assert_eq!(actual, expected, "position mismatch at frame {index}");
        prior_expected = Some(expected);
        assert_eq!(reader.offset - record_start, RECORD_BYTES);
    }
    assert_eq!(reader.offset, VECTOR.len());
}

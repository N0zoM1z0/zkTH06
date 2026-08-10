use zkth06_player_bullets::{
    spawn_reimu_a, InitializedBullet, SlotCarry, SpawnInput, Vec2Bits, Vec3Bits,
    BULLET_STATE_FIRED, PLAYER_BULLET_SLOTS,
};

const VECTOR: &[u8] = include_bytes!("../../../evidence/player-bullets-002677-2000-v1.bin");
const MAGIC: &[u8; 8] = b"ZKPBV1\0\0";
const HEADER_BYTES: usize = 224;
const RECORD_BYTES: usize = 416;
const ALLOCATION_BYTES: usize = 72;

struct Reader<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn take(&mut self, count: usize) -> &'a [u8] {
        let end = self.offset.checked_add(count).expect("reader offset overflow");
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

    fn i16(&mut self) -> i16 {
        i16::from_le_bytes(self.take(2).try_into().unwrap())
    }

    fn u32(&mut self) -> u32 {
        u32::from_le_bytes(self.take(4).try_into().unwrap())
    }

    fn i32(&mut self) -> i32 {
        i32::from_le_bytes(self.take(4).try_into().unwrap())
    }

    fn vec2(&mut self) -> Vec2Bits {
        Vec2Bits {
            x: self.u32(),
            y: self.u32(),
        }
    }

    fn vec3(&mut self) -> Vec3Bits {
        Vec3Bits {
            x: self.u32(),
            y: self.u32(),
            z: self.u32(),
        }
    }
}

fn read_allocation(reader: &mut Reader<'_>) -> InitializedBullet {
    let slot = reader.u8();
    let bullet_data_index = reader.u8();
    let bullet_type = reader.u8();
    let source_spawn_position_idx = reader.u8();
    let damage = reader.i16();
    let requested_anm_script = reader.u16();
    InitializedBullet {
        slot,
        bullet_data_index,
        position: reader.vec3(),
        size: reader.vec3(),
        velocity: reader.vec2(),
        sideways_motion_bits: reader.u32(),
        unk_134: reader.vec3(),
        timer_previous: reader.i32(),
        timer_subframe_bits: reader.u32(),
        timer_current: reader.i32(),
        damage,
        bullet_type,
        unk_152: reader.i16(),
        stored_spawn_position_idx: reader.i16(),
        source_spawn_position_idx,
        requested_anm_script,
    }
}

#[test]
fn local_spawn_transition_matches_every_retail_callback() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, RECORD_BYTES);
    assert_eq!(reader.u32(), 2_000);
    let spawn_calls = reader.u32() as usize;
    let initialized_bullets = reader.u32();
    assert_eq!(spawn_calls, 1_590);
    assert_eq!(initialized_bullets, 422);
    assert_eq!(reader.u8(), 0, "vector is not Reimu");
    assert_eq!(reader.u8(), 0, "vector is not shot type A");
    assert_eq!(reader.u8(), 3, "unexpected maximum power rank");
    assert_eq!(reader.u8(), 1, "unexpected vector profile flags");
    assert_eq!(reader.u32(), 35);
    assert_eq!(reader.u32(), 1_869);
    for _ in 0..5 {
        assert!(reader.take(32).iter().any(|byte| *byte != 0));
    }
    assert!(reader.take(20).iter().all(|byte| *byte == 0));
    assert_eq!(reader.offset, HEADER_BYTES);
    assert_eq!(VECTOR.len(), HEADER_BYTES + spawn_calls * RECORD_BYTES);

    let mut observed_allocations = 0_u32;
    let mut previous_frame = 0_u32;
    let mut rank_calls = [0_u32; 3];
    for _ in 0..spawn_calls {
        let record_start = reader.offset;
        let game_frame = reader.u32();
        assert!(game_frame > previous_frame);
        previous_frame = game_frame;
        let current_power = reader.u16();
        let timer = reader.u8();
        let _is_focus = reader.u8();
        let expected_count = reader.u8();
        assert_eq!(reader.u8(), 0, "nonzero record reserved byte");
        let player_position = reader.vec3();
        let orb_positions = [reader.vec3(), reader.vec3()];
        let mut slot_states = [0_u8; PLAYER_BULLET_SLOTS];
        for state in &mut slot_states {
            *state = reader.u8();
        }
        assert!(reader.take(2).iter().all(|byte| *byte == 0));

        let input = SpawnInput {
            timer,
            current_power,
            player_position,
            orb_positions,
            slot_states,
            slot_carry: [SlotCarry::default(); PLAYER_BULLET_SLOTS],
        };
        let output = spawn_reimu_a(input)
            .unwrap_or_else(|error| panic!("retail frame {game_frame} rejected: {error:?}"));
        assert_eq!(output.allocation_count, expected_count, "frame {game_frame}");
        let mut expected_states = slot_states;
        for allocation_index in 0..4 {
            let allocation_start = reader.offset;
            let expected = read_allocation(&mut reader);
            assert_eq!(reader.offset - allocation_start, ALLOCATION_BYTES);
            if allocation_index < usize::from(expected_count) {
                assert_eq!(
                    output.allocations[allocation_index], expected,
                    "allocation {allocation_index} at retail frame {game_frame}"
                );
                expected_states[usize::from(expected.slot)] = BULLET_STATE_FIRED;
            } else {
                assert_eq!(expected, InitializedBullet::default());
            }
        }
        assert_eq!(output.slot_states, expected_states, "frame {game_frame}");
        observed_allocations += u32::from(expected_count);
        rank_calls[if current_power < 8 {
            0
        } else if current_power < 16 {
            1
        } else {
            2
        }] += 1;
        assert_eq!(reader.offset - record_start, RECORD_BYTES);
    }
    assert_eq!(observed_allocations, initialized_bullets);
    assert_eq!(rank_calls, [953, 324, 313]);
    assert_eq!(reader.offset, VECTOR.len());
}

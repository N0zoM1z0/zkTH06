use zkth06_player_motion::enclosing::{EnclosingPlayerState, PlayerConfig, PlayerLifeState};
use zkth06_player_motion::Position;
use zkth06_player_shooting::{
    retail_shooting_anchor_state, step_shooting_player, FireBulletTimer, ShootingPlayerState,
};

const VECTOR: &[u8] = include_bytes!("../../../evidence/player-shooting-002677-2000-v1.bin");
const MAGIC: &[u8; 8] = b"ZKSHV1\0\0";
const HEADER_BYTES: usize = 192;
const RECORD_BYTES: usize = 32;
const NO_SPAWN: u8 = 0xff;

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

    fn i32(&mut self) -> i32 {
        i32::from_le_bytes(self.take(4).try_into().unwrap())
    }
}

struct ExpectedRecord {
    index: u32,
    input: u16,
    state: ShootingPlayerState,
    spawn_timer: u8,
}

fn read_record(reader: &mut Reader<'_>, spawn_call_count: u32) -> ExpectedRecord {
    let index = reader.u32();
    let input = reader.u16();
    let life_state = match reader.u8() {
        0 => PlayerLifeState::Alive,
        3 => PlayerLifeState::Invulnerable,
        value => panic!("unsupported retail life state {value}"),
    };
    let flags = reader.u8();
    assert_eq!(flags & !0x0f, 0);
    let invulnerability_timer = reader.i32();
    let x_bits = reader.u32();
    let y_bits = reader.u32();
    let previous_frame_input = reader.u16();
    let spawn_timer = reader.u8();
    assert_eq!(reader.u8(), 0, "nonzero record reserved byte");
    let fire_previous = reader.i32();
    let fire_current = reader.i32();
    ExpectedRecord {
        index,
        input,
        state: ShootingPlayerState {
            enclosing: EnclosingPlayerState {
                game_frame: index + 1,
                position: Position { x_bits, y_bits },
                life_state,
                invulnerability_timer,
                is_time_stopped: flags & 1 != 0,
                bomb_active: flags & 2 != 0,
            },
            is_focus: flags & 4 != 0,
            previous_frame_input,
            fire_bullet_timer: FireBulletTimer {
                previous: fire_previous,
                current: fire_current,
            },
            spawn_call_count,
        },
        spawn_timer,
    }
}

#[test]
fn shooting_projection_matches_every_retail_transition_and_callback_request() {
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
    assert_eq!(reader.u8(), 0, "nonzero header reserved byte");
    assert_eq!(reader.u32(), 1, "unexpected anchor game frame");
    for _ in 0..5 {
        assert!(reader.take(32).iter().any(|byte| *byte != 0));
    }
    assert_eq!(reader.offset, HEADER_BYTES);
    assert_eq!(VECTOR.len(), HEADER_BYTES + source_frames * RECORD_BYTES);

    let initial = read_record(&mut reader, 0);
    assert_eq!(initial.index, 0);
    assert_eq!(initial.spawn_timer, NO_SPAWN);
    let mut actual = retail_shooting_anchor_state(config).unwrap();
    assert_eq!(actual, initial.state);

    for expected_index in 1..source_frames {
        let record_start = reader.offset;
        let current_count = actual.spawn_call_count;
        let mut expected = read_record(&mut reader, current_count);
        assert_eq!(expected.index as usize, expected_index);
        if expected.spawn_timer != NO_SPAWN {
            expected.state.spawn_call_count += 1;
        }
        let (next, effect) = step_shooting_player(config, actual, expected.input)
            .unwrap_or_else(|error| panic!("frame {} rejected: {error:?}", expected.index + 1));
        assert_eq!(
            effect.spawn_bullets_timer,
            (expected.spawn_timer != NO_SPAWN).then_some(expected.spawn_timer),
            "callback mismatch at frame {}",
            expected.index + 1
        );
        assert_eq!(effect.focused_callback, expected.state.is_focus);
        assert_eq!(
            next,
            expected.state,
            "state mismatch at frame {}",
            expected.index + 1
        );
        assert_eq!(reader.offset - record_start, RECORD_BYTES);
        actual = next;
    }
    assert_eq!(reader.offset, VECTOR.len());
    assert_eq!(actual.enclosing.game_frame, 2_000);
    assert_eq!(actual.spawn_call_count, 1_590);
    assert_eq!(actual.fire_bullet_timer.current, -1);
}

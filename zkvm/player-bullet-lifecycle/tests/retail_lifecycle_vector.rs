use zkth06_player_bullet_lifecycle::{
    reimu_a, retail_lifecycle_anchor_state, step_player_bullet_lifecycle, ActiveBullet, BulletPool,
    FullSpeedTimer, PlayerBulletLifecycleState, PROFILE_LAST_GAME_FRAME,
};
use zkth06_player_bullets::{SlotCarry, Vec2Bits, Vec3Bits, PLAYER_BULLET_SLOTS};
use zkth06_player_motion::enclosing::{EnclosingPlayerState, PlayerLifeState};
use zkth06_player_motion::Position;
use zkth06_player_shooting::{FireBulletTimer, ShootingPlayerState};

const VECTOR: &[u8] = include_bytes!("../../../evidence/player-bullet-lifecycle-002677-207-v1.bin");
const MAGIC: &[u8; 8] = b"ZKPLV1\0\0";
const HEADER_BYTES: usize = 232;
const FRAME_BYTES: usize = 40;
const BULLET_BYTES: usize = 104;
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
        let end = self.offset.checked_add(count).expect("reader overflow");
        let result = self.bytes.get(self.offset..end).expect("truncated vector");
        self.offset = end;
        result
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

struct ExpectedFrame {
    game_frame: u32,
    input: u16,
    spawn_timer: u8,
    state: PlayerBulletLifecycleState,
}

fn read_bullet(reader: &mut Reader<'_>) -> (usize, ActiveBullet) {
    let start = reader.offset;
    let slot = usize::from(reader.u8());
    let bullet_type = reader.u8();
    let damage = reader.i16();
    let unk_152 = reader.i16();
    let spawn_position_idx = reader.i16();
    let position = reader.vec3();
    let size = reader.vec3();
    let velocity = reader.vec2();
    let sideways_motion_bits = reader.u32();
    let unk_134 = reader.vec3();
    let age = FullSpeedTimer {
        previous: reader.i32(),
        current: {
            assert_eq!(reader.u32(), 0, "nonzero age subframe");
            reader.i32()
        },
    };
    let sprite_position = reader.vec3();
    let sprite_timer = FullSpeedTimer {
        previous: reader.i32(),
        current: reader.i32(),
    };
    let sprite_flags = reader.u32();
    let sprite_active_index = reader.u16();
    let sprite_anm_file_index = reader.u16();
    let sprite_width_bits = reader.u32();
    let sprite_height_bits = reader.u32();
    assert_eq!(reader.offset - start, BULLET_BYTES);
    (
        slot,
        ActiveBullet {
            position,
            size,
            velocity,
            sideways_motion_bits,
            unk_134,
            age,
            damage,
            bullet_type,
            unk_152,
            spawn_position_idx,
            sprite_position,
            sprite_timer,
            sprite_flags,
            sprite_active_index,
            sprite_anm_file_index,
            sprite_width_bits,
            sprite_height_bits,
        },
    )
}

fn read_frame(reader: &mut Reader<'_>) -> ExpectedFrame {
    let prefix_start = reader.offset;
    let game_frame = reader.u32();
    let input = reader.u16();
    let player_state = match reader.u8() {
        0 => PlayerLifeState::Alive,
        3 => PlayerLifeState::Invulnerable,
        value => panic!("unsupported Player state {value}"),
    };
    let flags = reader.u8();
    assert_eq!(flags & !0x07, 0);
    let invulnerability_timer = reader.i32();
    let x_bits = reader.u32();
    let y_bits = reader.u32();
    let previous_frame_input = reader.u16();
    let spawn_timer = reader.u8();
    assert_eq!(reader.u8(), 0, "nonzero frame reserved byte");
    let fire_previous = reader.i32();
    let fire_current = reader.i32();
    let spawn_call_count = reader.u32();
    let active_count = reader.u8();
    assert!(reader.take(3).iter().all(|value| *value == 0));
    assert_eq!(reader.offset - prefix_start, FRAME_BYTES);

    let mut slots = [None; PLAYER_BULLET_SLOTS];
    let mut prior_slot = None;
    for _ in 0..active_count {
        let (slot, bullet) = read_bullet(reader);
        assert!(slot < PLAYER_BULLET_SLOTS);
        assert!(prior_slot.is_none_or(|prior| slot > prior));
        assert!(slots[slot].replace(bullet).is_none());
        prior_slot = Some(slot);
    }
    ExpectedFrame {
        game_frame,
        input,
        spawn_timer,
        state: PlayerBulletLifecycleState {
            shooting: ShootingPlayerState {
                enclosing: EnclosingPlayerState {
                    game_frame,
                    position: Position { x_bits, y_bits },
                    life_state: player_state,
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
            bullets: BulletPool {
                slots,
                carry: [SlotCarry::default(); PLAYER_BULLET_SLOTS],
            },
        },
    }
}

#[test]
fn enclosing_lifecycle_matches_every_retail_frame_without_slot_witnesses() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, FRAME_BYTES);
    assert_eq!(reader.u32() as usize, BULLET_BYTES);
    assert_eq!(reader.u32(), 2_000);
    let selected_frames = reader.u32();
    assert_eq!(selected_frames, PROFILE_LAST_GAME_FRAME);
    assert_eq!(reader.u8(), 0, "vector is not Reimu");
    assert_eq!(reader.u8(), 0, "vector is not shot type A");
    assert_eq!(reader.u8(), 1, "unexpected lifecycle profile flags");
    assert_eq!(reader.u8(), 0, "nonzero header reserved byte");
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME);
    assert_eq!(reader.u32(), 208);
    assert_eq!(reader.u32(), 7);
    for _ in 0..5 {
        assert!(reader.take(32).iter().any(|byte| *byte != 0));
    }
    assert!(reader.take(20).iter().all(|byte| *byte == 0));
    assert_eq!(reader.offset, HEADER_BYTES);

    let first = read_frame(&mut reader);
    assert_eq!(first.game_frame, 1);
    assert_eq!(first.spawn_timer, NO_SPAWN);
    let mut actual = retail_lifecycle_anchor_state(reimu_a()).unwrap();
    assert_eq!(actual, first.state);

    let mut observed_spawns = 0_u32;
    let mut maximum_active = 0_usize;
    for expected_index in 1..selected_frames {
        let expected = read_frame(&mut reader);
        assert_eq!(expected.game_frame, expected_index + 1);
        actual = step_player_bullet_lifecycle(reimu_a(), actual, expected.input)
            .unwrap_or_else(|error| panic!("frame {} rejected: {error:?}", expected.game_frame));
        let next_active = actual.bullets.slots.iter().flatten().count();
        observed_spawns += u32::from(expected.spawn_timer != NO_SPAWN);
        maximum_active = maximum_active.max(next_active);
        assert_eq!(
            actual, expected.state,
            "lifecycle mismatch at frame {}",
            expected.game_frame
        );
    }
    assert_eq!(reader.offset, VECTOR.len());
    assert_eq!(
        actual.shooting.enclosing.game_frame,
        PROFILE_LAST_GAME_FRAME
    );
    assert_eq!(actual.shooting.spawn_call_count, 173);
    assert_eq!(observed_spawns, 173);
    assert_eq!(maximum_active, 7);
    // Exact allocation/reclamation totals are also checked by the vector
    // generator; the final derived pool contains 35 - 30 = 5 bullets.
    assert_eq!(actual.bullets.slots.iter().flatten().count(), 5);
}

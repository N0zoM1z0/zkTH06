use zkth06_early_gameplay::{
    player_bullet_state, retail_early_gameplay_anchor, step_early_gameplay, EarlyEnemy,
    EarlyGameplayState, EARLY_ENEMY_SLOTS, PROFILE_LAST_GAME_FRAME,
};
use zkth06_player_bullet_lifecycle::{Vec2Bits, Vec3Bits};

const VECTOR: &[u8] = include_bytes!("../../../evidence/early-gameplay-002677-208-v1.bin");
const MAGIC: &[u8; 8] = b"ZKEGP1\0\0";
const HEADER_BYTES: usize = 228;
const FRAME_BYTES: usize = 24;
const ENEMY_BYTES: usize = 40;
const NO_COLLISION: u8 = 0xff;

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
            .expect("reader offset overflow");
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

struct ExpectedFrame {
    game_frame: u32,
    input: u16,
    enemy_count: u8,
    collided_slot: u8,
    score: u32,
    last_enemy_hit: Vec3Bits,
}

fn read_frame(reader: &mut Reader<'_>) -> ExpectedFrame {
    ExpectedFrame {
        game_frame: reader.u32(),
        input: reader.u16(),
        enemy_count: reader.u8(),
        collided_slot: reader.u8(),
        score: reader.u32(),
        last_enemy_hit: Vec3Bits {
            x: reader.u32(),
            y: reader.u32(),
            z: reader.u32(),
        },
    }
}

fn read_enemy(reader: &mut Reader<'_>) -> (usize, EarlyEnemy) {
    let slot = usize::from(reader.u8());
    let has_been_in_bounds = reader.u8() != 0;
    assert_eq!(reader.u16(), 0, "nonzero Enemy reserved field");
    let ecl_time = reader.i32();
    let life = reader.i32();
    let position = Vec3Bits {
        x: reader.u32(),
        y: reader.u32(),
        z: reader.u32(),
    };
    let axis_speed = Vec2Bits {
        x: reader.u32(),
        y: reader.u32(),
    };
    let angle_bits = reader.u32();
    let angular_velocity_bits = reader.u32();
    (
        slot,
        EarlyEnemy {
            position,
            axis_speed,
            angle_bits,
            angular_velocity_bits,
            ecl_time,
            life,
            has_been_in_bounds,
        },
    )
}

fn assert_frame(reader: &mut Reader<'_>, state: &EarlyGameplayState, expected: ExpectedFrame) {
    assert_eq!(
        state.player.shooting.enclosing.game_frame,
        expected.game_frame
    );
    assert_eq!(
        state.score, expected.score,
        "score at frame {}",
        expected.game_frame
    );
    assert_eq!(
        state.last_enemy_hit, expected.last_enemy_hit,
        "target at frame {}",
        expected.game_frame
    );
    assert_eq!(
        state.collided_slot.map_or(NO_COLLISION, |slot| slot),
        expected.collided_slot,
        "collision slot at frame {}",
        expected.game_frame
    );
    assert_eq!(
        state.enemies.iter().flatten().count(),
        usize::from(expected.enemy_count),
        "Enemy count at frame {}",
        expected.game_frame
    );
    let mut prior_slot = None;
    for _ in 0..expected.enemy_count {
        let (slot, enemy) = read_enemy(reader);
        assert!(slot < EARLY_ENEMY_SLOTS);
        assert!(prior_slot.is_none_or(|prior| slot > prior));
        assert_eq!(
            state.enemies[slot],
            Some(enemy),
            "Enemy slot {slot} at frame {}",
            expected.game_frame
        );
        prior_slot = Some(slot);
    }
}

#[test]
fn enclosing_enemy_transition_crosses_the_first_collision_without_enemy_witnesses() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, FRAME_BYTES);
    assert_eq!(reader.u32() as usize, ENEMY_BYTES);
    assert_eq!(reader.u32(), 225);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME - 1);
    for _ in 0..6 {
        assert!(reader.take(32).iter().any(|byte| *byte != 0));
    }
    assert_eq!(reader.offset, HEADER_BYTES);

    let first = read_frame(&mut reader);
    assert_eq!(first.game_frame, 1);
    let mut state = retail_early_gameplay_anchor().unwrap();
    assert_frame(&mut reader, &state, first);

    for game_frame in 2..=PROFILE_LAST_GAME_FRAME {
        let expected = read_frame(&mut reader);
        assert_eq!(expected.game_frame, game_frame);
        state = step_early_gameplay(state, expected.input)
            .unwrap_or_else(|error| panic!("frame {game_frame} rejected: {error:?}"));
        assert_frame(&mut reader, &state, expected);
    }
    assert_eq!(reader.offset, VECTOR.len());

    assert_eq!(state.score, 390);
    assert_eq!(state.last_enemy_hit.x, 0x42c2_170b);
    assert_eq!(state.last_enemy_hit.y, 0x42e6_9ce3);
    assert_eq!(state.collided_slot, Some(2));
    assert_eq!(state.enemies.iter().flatten().count(), 4);
    assert_eq!(player_bullet_state(&state, 2), 2);
    let collided = state.player.bullets.slots[2].unwrap();
    assert_eq!(
        collided.position,
        Vec3Bits {
            x: 0x42db_f378,
            y: 0x42fb_f378,
            z: 0x3dcc_cccd
        }
    );
    assert_eq!(
        collided.velocity,
        Vec2Bits {
            x: 0xb38c_cde2,
            y: 0xbfc0_0000
        }
    );
    assert_eq!(collided.sprite_position.z, 0x3efd_70a4);
    assert_eq!(collided.sprite_active_index, 1090);
    assert_eq!(collided.sprite_anm_file_index, 1120);
    assert_eq!(collided.sprite_width_bits, 0x4180_0000);
    assert_eq!(collided.sprite_height_bits, 0x4180_0000);
    assert_eq!(collided.sprite_flags, 0x1007);
    assert_eq!(
        (
            collided.sprite_timer.previous,
            collided.sprite_timer.current
        ),
        (0, 1)
    );
    assert_eq!((collided.age.previous, collided.age.current), (7, 8));
}

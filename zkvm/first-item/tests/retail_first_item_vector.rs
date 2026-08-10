use zkth06_early_gameplay::{
    player_bullet_state, retail_early_gameplay_anchor, step_early_gameplay, EarlyEnemy,
    EarlyGameplayState, EARLY_ENEMY_SLOTS,
};
use zkth06_first_item::{
    from_first_collision, step_first_item, ActiveItem, FirstItemState, PROFILE_LAST_GAME_FRAME,
};
use zkth06_player_bullet_lifecycle::{ActiveBullet, FullSpeedTimer, Vec2Bits, Vec3Bits};
use zkth06_player_bullets::{BULLET_STATE_UNUSED, PLAYER_BULLET_SLOTS};

const VECTOR: &[u8] = include_bytes!("../../../evidence/first-item-002677-249-v1.bin");
const MAGIC: &[u8; 8] = b"ZKFIV1\0\0";
const HEADER_BYTES: usize = 236;
const FRAME_BYTES: usize = 40;
const ENEMY_BYTES: usize = 40;
const BULLET_BYTES: usize = 104;
const ITEM_BYTES: usize = 52;

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
    active_bullets: usize,
    score: u32,
    target: Vec3Bits,
    enemies: usize,
    collisions: usize,
    active_items: usize,
    random_spawn_index: u8,
    current_power: u16,
    subrank: i32,
    item_next_index: u16,
    random_table_index: u8,
    item_count: u8,
}

fn read_frame(reader: &mut Reader<'_>) -> ExpectedFrame {
    let frame = ExpectedFrame {
        game_frame: reader.u32(),
        input: reader.u16(),
        active_bullets: usize::from(reader.u16()),
        score: reader.u32(),
        target: reader.vec3(),
        enemies: usize::from(reader.u8()),
        collisions: usize::from(reader.u8()),
        active_items: usize::from(reader.u8()),
        random_spawn_index: reader.u8(),
        current_power: reader.u16(),
        subrank: reader.i32(),
        item_next_index: reader.u16(),
        random_table_index: reader.u8(),
        item_count: reader.u8(),
    };
    assert_eq!(reader.u16(), 0, "nonzero frame reserved field");
    frame
}

fn read_enemy(reader: &mut Reader<'_>) -> (usize, EarlyEnemy) {
    let slot = usize::from(reader.u8());
    let has_been_in_bounds = reader.u8() != 0;
    assert_eq!(reader.u16(), 0, "nonzero Enemy reserved field");
    let ecl_time = reader.i32();
    let life = reader.i32();
    let position = reader.vec3();
    let axis_speed = reader.vec2();
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

fn read_bullet(reader: &mut Reader<'_>) -> (usize, u8, ActiveBullet) {
    let slot = usize::from(reader.u8());
    let state = reader.u8();
    assert_eq!(reader.u16(), 0, "nonzero bullet reserved field");
    let position = reader.vec3();
    let size = reader.vec3();
    let velocity = reader.vec2();
    let sideways_motion_bits = reader.u32();
    let unk_134 = reader.vec3();
    let age = FullSpeedTimer {
        previous: reader.i32(),
        current: reader.i32(),
    };
    let damage = reader.i16();
    let bullet_type = reader.u8();
    assert_eq!(reader.u8(), 0, "nonzero bullet padding field");
    let unk_152 = reader.i16();
    let spawn_position_idx = reader.i16();
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
    (
        slot,
        state,
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

fn read_item(reader: &mut Reader<'_>) -> (usize, ActiveItem) {
    let slot = usize::from(reader.u8());
    let item_type = reader.u8();
    assert_eq!(reader.u16(), 0, "nonzero Item reserved field");
    let current_position = reader.vec3();
    let start_position = reader.vec3();
    let target_position = reader.vec3();
    let timer = FullSpeedTimer {
        previous: reader.i32(),
        current: reader.i32(),
    };
    let state = reader.u8();
    let unk_142 = reader.u8();
    assert_eq!(reader.u8(), 1, "active Item is_in_use must be one");
    assert_eq!(reader.u8(), 0, "nonzero Item padding field");
    (
        slot,
        ActiveItem {
            current_position,
            start_position,
            target_position,
            timer,
            item_type,
            state,
            unk_142,
        },
    )
}

fn assert_enemies(
    reader: &mut Reader<'_>,
    actual: &[Option<EarlyEnemy>; EARLY_ENEMY_SLOTS],
    expected: &ExpectedFrame,
) {
    assert_eq!(actual.iter().flatten().count(), expected.enemies);
    let mut prior = None;
    for _ in 0..expected.enemies {
        let (slot, enemy) = read_enemy(reader);
        assert!(slot < EARLY_ENEMY_SLOTS && prior.is_none_or(|value| slot > value));
        assert_eq!(
            actual[slot],
            Some(enemy),
            "Enemy slot {slot} at frame {}",
            expected.game_frame
        );
        prior = Some(slot);
    }
}

fn assert_bullets(
    reader: &mut Reader<'_>,
    actual: &[Option<ActiveBullet>; PLAYER_BULLET_SLOTS],
    states: impl Fn(usize) -> u8,
    expected: &ExpectedFrame,
) {
    assert_eq!(actual.iter().flatten().count(), expected.active_bullets);
    let mut collisions = 0_usize;
    let mut prior = None;
    for _ in 0..expected.active_bullets {
        let (slot, state, bullet) = read_bullet(reader);
        assert!(slot < PLAYER_BULLET_SLOTS && prior.is_none_or(|value| slot > value));
        assert_eq!(
            states(slot),
            state,
            "bullet state slot {slot}, frame {}",
            expected.game_frame
        );
        assert_eq!(
            actual[slot],
            Some(bullet),
            "bullet slot {slot}, frame {}",
            expected.game_frame
        );
        collisions += usize::from(state == 2);
        prior = Some(slot);
    }
    assert_eq!(collisions, expected.collisions);
    for (slot, bullet) in actual.iter().enumerate() {
        if bullet.is_none() {
            assert_eq!(states(slot), BULLET_STATE_UNUSED);
        }
    }
}

fn assert_early(reader: &mut Reader<'_>, state: &EarlyGameplayState, expected: &ExpectedFrame) {
    assert_eq!(
        state.player.shooting.enclosing.game_frame,
        expected.game_frame
    );
    assert_eq!(state.score, expected.score);
    assert_eq!(state.last_enemy_hit, expected.target);
    assert_eq!(expected.current_power, 0);
    assert_eq!(expected.subrank, 0);
    assert_eq!(expected.active_items, 0);
    assert_enemies(reader, &state.enemies, expected);
    assert_bullets(
        reader,
        &state.player.bullets.slots,
        |slot| player_bullet_state(state, slot),
        expected,
    );
}

fn assert_first_item(reader: &mut Reader<'_>, state: &FirstItemState, expected: &ExpectedFrame) {
    assert_eq!(
        state.wave.player.shooting.enclosing.game_frame,
        expected.game_frame
    );
    assert_eq!(
        state.wave.score, expected.score,
        "score at frame {}",
        expected.game_frame
    );
    assert_eq!(state.wave.last_enemy_hit, expected.target);
    assert_eq!(state.current_power, expected.current_power);
    assert_eq!(state.subrank, expected.subrank);
    assert_eq!(state.random_item_spawn_index, expected.random_spawn_index);
    assert_eq!(state.random_item_table_index, expected.random_table_index);
    assert_eq!(state.item_next_index, expected.item_next_index);
    assert_eq!(state.item_count, u16::from(expected.item_count));
    assert_enemies(reader, &state.wave.enemies, expected);
    assert_bullets(
        reader,
        &state.wave.player.bullets.slots,
        |slot| state.wave.bullet_states[slot],
        expected,
    );
    assert_eq!(usize::from(state.item.is_some()), expected.active_items);
    if expected.active_items == 1 {
        let (slot, item) = read_item(reader);
        assert_eq!(slot, 0);
        assert_eq!(
            state.item,
            Some(item),
            "Item state at frame {}",
            expected.game_frame
        );
    }
}

#[test]
fn replay_inputs_derive_first_item_spawn_motion_and_feedback() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, FRAME_BYTES);
    assert_eq!(reader.u32() as usize, ENEMY_BYTES);
    assert_eq!(reader.u32() as usize, BULLET_BYTES);
    assert_eq!(reader.u32() as usize, ITEM_BYTES);
    assert_eq!(reader.u32(), 300);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME - 1);
    for _ in 0..6 {
        assert!(reader.take(32).iter().any(|byte| *byte != 0));
    }
    assert_eq!(reader.offset, HEADER_BYTES);

    let first = read_frame(&mut reader);
    assert_eq!(first.game_frame, 1);
    let mut early = retail_early_gameplay_anchor().unwrap();
    assert_early(&mut reader, &early, &first);
    for game_frame in 2..=208 {
        let expected = read_frame(&mut reader);
        assert_eq!(expected.game_frame, game_frame);
        early = step_early_gameplay(early, expected.input)
            .unwrap_or_else(|error| panic!("early frame {game_frame} rejected: {error:?}"));
        assert_early(&mut reader, &early, &expected);
    }

    let mut state = from_first_collision(early).unwrap();
    assert_eq!(state.random_item_spawn_index, 2);
    for game_frame in 209..=PROFILE_LAST_GAME_FRAME {
        let expected = read_frame(&mut reader);
        assert_eq!(expected.game_frame, game_frame);
        state = step_first_item(state, expected.input)
            .unwrap_or_else(|error| panic!("first-Item frame {game_frame} rejected: {error:?}"));
        assert_first_item(&mut reader, &state, &expected);
    }
    assert_eq!(reader.offset, VECTOR.len());
    assert_eq!(state.wave.score, 1960);
    assert_eq!(state.current_power, 1);
    assert_eq!(state.subrank, 1);
    assert!(state.item.is_none());
    assert_eq!(state.item_count, 1);
    assert_eq!(state.random_item_spawn_index, 6);
    assert_eq!(state.random_item_table_index, 1);
}

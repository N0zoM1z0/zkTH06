use zkth06_first_item::ActiveItem;
use zkth06_player_bullet_lifecycle::{ActiveBullet, FullSpeedTimer, Vec2Bits, Vec3Bits};
use zkth06_player_bullets::{BULLET_STATE_COLLIDED, BULLET_STATE_UNUSED, PLAYER_BULLET_SLOTS};
use zkth06_second_wave::{
    derive_second_wave_anchor, step_second_wave, SecondWaveEnemy, SecondWaveState,
    PROFILE_LAST_GAME_FRAME,
};

const VECTOR: &[u8] = include_bytes!("../../../evidence/second-wave-002677-350-v1.bin");
const MAGIC: &[u8; 8] = b"ZKSWV1\0\0";
const HEADER_BYTES: usize = 240;
const FRAME_BYTES: usize = 56;
const ENEMY_BYTES: usize = 40;
const BULLET_BYTES: usize = 104;
const ITEM_BYTES: usize = 52;

struct Reader<'a> {
    data: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(data: &'a [u8]) -> Self { Self { data, offset: 0 } }
    fn take(&mut self, count: usize) -> &'a [u8] {
        let result = &self.data[self.offset..self.offset + count];
        self.offset += count;
        result
    }
    fn u8(&mut self) -> u8 { self.take(1)[0] }
    fn u16(&mut self) -> u16 { u16::from_le_bytes(self.take(2).try_into().unwrap()) }
    fn i16(&mut self) -> i16 { i16::from_le_bytes(self.take(2).try_into().unwrap()) }
    fn u32(&mut self) -> u32 { u32::from_le_bytes(self.take(4).try_into().unwrap()) }
    fn i32(&mut self) -> i32 { i32::from_le_bytes(self.take(4).try_into().unwrap()) }
    fn vec3(&mut self) -> Vec3Bits { Vec3Bits { x: self.u32(), y: self.u32(), z: self.u32() } }
}

struct ExpectedFrame {
    game_frame: u32,
    score: u32,
    last_hit: Vec3Bits,
    rng_seed: u16,
    rng_generation: u32,
    random_spawn: u8,
    random_table: u8,
    item_next: u16,
    item_count: u16,
    subrank: i32,
    power: u16,
    enemy_count: usize,
    item_active: usize,
    bullet_active: usize,
    collided: usize,
    enemy_bullet_next: u16,
    enemy_bullet_count: u16,
    enemy_bullet_timer_previous: i32,
    enemy_bullet_timer_current: i32,
    enemy_bullet_active: u16,
}

fn read_frame(reader: &mut Reader<'_>) -> ExpectedFrame {
    ExpectedFrame {
        game_frame: reader.u32(), score: reader.u32(), last_hit: reader.vec3(),
        rng_seed: reader.u16(), rng_generation: reader.u32(),
        random_spawn: reader.u8(), random_table: reader.u8(),
        item_next: reader.u16(), item_count: reader.u16(), subrank: reader.i32(), power: reader.u16(),
        enemy_count: reader.u8() as usize, item_active: reader.u8() as usize,
        bullet_active: reader.u8() as usize, collided: reader.u8() as usize,
        enemy_bullet_next: reader.u16(), enemy_bullet_count: reader.u16(),
        enemy_bullet_timer_previous: reader.i32(), enemy_bullet_timer_current: reader.i32(),
        enemy_bullet_active: reader.u16(),
    }
}

fn read_enemy(reader: &mut Reader<'_>) -> (usize, SecondWaveEnemy) {
    let slot = reader.u8() as usize;
    let has_been_in_bounds = reader.u8() != 0;
    assert_eq!(reader.u16(), 0);
    let current = reader.i32();
    let life = reader.i32();
    let position = reader.vec3();
    let axis_speed = Vec2Bits { x: reader.u32(), y: reader.u32() };
    let angle_bits = reader.u32();
    let angular_velocity_bits = reader.u32();
    (slot, SecondWaveEnemy {
        position, axis_speed, angle_bits, angular_velocity_bits,
        ecl_timer: FullSpeedTimer { previous: current - 1, current }, life, has_been_in_bounds,
    })
}

fn read_bullet(reader: &mut Reader<'_>) -> (usize, u8, ActiveBullet) {
    let slot = reader.u8() as usize;
    let state = reader.u8();
    assert_eq!(reader.u16(), 0);
    let position = reader.vec3();
    let size = reader.vec3();
    let velocity = Vec2Bits { x: reader.u32(), y: reader.u32() };
    let sideways_motion_bits = reader.u32();
    let unk_134 = reader.vec3();
    let age = FullSpeedTimer { previous: reader.i32(), current: reader.i32() };
    let damage = reader.i16();
    let bullet_type = reader.u8();
    assert_eq!(reader.u8(), 0);
    let unk_152 = reader.i16();
    let spawn_position_idx = reader.i16();
    let sprite_position = reader.vec3();
    let sprite_timer = FullSpeedTimer { previous: reader.i32(), current: reader.i32() };
    let sprite_flags = reader.u32();
    let sprite_active_index = reader.u16();
    let sprite_anm_file_index = reader.u16();
    let sprite_width_bits = reader.u32();
    let sprite_height_bits = reader.u32();
    (slot, state, ActiveBullet {
        position, size, velocity, sideways_motion_bits, unk_134, age, damage, bullet_type,
        unk_152, spawn_position_idx, sprite_position, sprite_timer, sprite_flags,
        sprite_active_index, sprite_anm_file_index, sprite_width_bits, sprite_height_bits,
    })
}

fn read_item(reader: &mut Reader<'_>) -> (usize, ActiveItem) {
    let slot = reader.u8() as usize;
    let item_type = reader.u8();
    assert_eq!(reader.u16(), 0);
    let current_position = reader.vec3();
    let start_position = reader.vec3();
    let target_position = reader.vec3();
    let timer = FullSpeedTimer { previous: reader.i32(), current: reader.i32() };
    let state = reader.u8();
    let unk_142 = reader.u8();
    assert_eq!(reader.u8(), 1);
    assert_eq!(reader.u8(), 0);
    (slot, ActiveItem { current_position, start_position, target_position, timer, item_type, state, unk_142 })
}

fn assert_frame(reader: &mut Reader<'_>, state: &SecondWaveState, expected: &ExpectedFrame) {
    assert_eq!(state.first_item.wave.player.shooting.enclosing.game_frame, expected.game_frame);
    assert_eq!(state.first_item.wave.score, expected.score);
    assert_eq!(state.first_item.wave.last_enemy_hit, expected.last_hit, "last hit at frame {}", expected.game_frame);
    assert_eq!(state.rng.seed, expected.rng_seed);
    assert_eq!(state.rng.generation, expected.rng_generation);
    assert_eq!(state.first_item.random_item_spawn_index, expected.random_spawn);
    assert_eq!(state.first_item.random_item_table_index, expected.random_table);
    assert_eq!(state.first_item.item_next_index, expected.item_next);
    assert_eq!(state.first_item.item_count, expected.item_count);
    assert_eq!(state.first_item.subrank, expected.subrank);
    assert_eq!(state.first_item.current_power, expected.power);
    assert_eq!(state.enemy_bullets.next_index, expected.enemy_bullet_next);
    assert_eq!(state.enemy_bullets.bullet_count, expected.enemy_bullet_count);
    assert_eq!(state.enemy_bullets.timer.previous, expected.enemy_bullet_timer_previous);
    assert_eq!(state.enemy_bullets.timer.current, expected.enemy_bullet_timer_current);
    assert_eq!(state.enemy_bullets.active_count, expected.enemy_bullet_active);

    let mut expected_enemies = [None; 5];
    for _ in 0..expected.enemy_count {
        let (slot, enemy) = read_enemy(reader);
        expected_enemies[slot] = Some(enemy);
    }
    assert_eq!(state.enemies, expected_enemies, "Enemy state at frame {}", expected.game_frame);

    let mut expected_bullets = [None; PLAYER_BULLET_SLOTS];
    let mut expected_states = [BULLET_STATE_UNUSED; PLAYER_BULLET_SLOTS];
    for _ in 0..expected.bullet_active {
        let (slot, bullet_state, bullet) = read_bullet(reader);
        expected_states[slot] = bullet_state;
        expected_bullets[slot] = Some(bullet);
    }
    assert_eq!(state.first_item.wave.bullet_states, expected_states, "bullet states at frame {}", expected.game_frame);
    assert_eq!(state.first_item.wave.player.bullets.slots, expected_bullets, "bullets at frame {}", expected.game_frame);
    assert_eq!(expected_states.iter().filter(|&&value| value == BULLET_STATE_COLLIDED).count(), expected.collided);

    let mut expected_items = [None; 4];
    for _ in 0..expected.item_active {
        let (slot, item) = read_item(reader);
        expected_items[slot] = Some(item);
    }
    assert_eq!(state.items, expected_items, "Items at frame {}", expected.game_frame);
}

#[test]
fn replay_inputs_derive_second_wave_rng_items_and_empty_enemy_bullets() {
    let mut reader = Reader::new(VECTOR);
    assert_eq!(reader.take(8), MAGIC);
    assert_eq!(reader.u32(), 1);
    assert_eq!(reader.u32() as usize, HEADER_BYTES);
    assert_eq!(reader.u32() as usize, FRAME_BYTES);
    assert_eq!(reader.u32() as usize, ENEMY_BYTES);
    assert_eq!(reader.u32() as usize, BULLET_BYTES);
    assert_eq!(reader.u32() as usize, ITEM_BYTES);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME);
    assert_eq!(reader.u32(), 250);
    assert_eq!(reader.u32(), 101);
    assert_eq!(reader.u32(), PROFILE_LAST_GAME_FRAME);
    for _ in 0..6 { assert!(reader.take(32).iter().any(|byte| *byte != 0)); }
    assert_eq!(reader.offset, HEADER_BYTES);

    let mut inputs = [0_u16; PROFILE_LAST_GAME_FRAME as usize];
    for input in &mut inputs { *input = reader.u16(); }
    let mut state = derive_second_wave_anchor(&inputs).unwrap();
    assert_eq!(state.first_item.wave.player.shooting.enclosing.game_frame, 249);
    for game_frame in 250..=PROFILE_LAST_GAME_FRAME {
        let expected = read_frame(&mut reader);
        assert_eq!(expected.game_frame, game_frame);
        state = step_second_wave(state, inputs[game_frame as usize - 1])
            .unwrap_or_else(|error| panic!("second-wave frame {game_frame} rejected: {error:?}"));
        assert_frame(&mut reader, &state, &expected);
    }
    assert_eq!(reader.offset, VECTOR.len());
    assert_eq!(state.first_item.wave.score, 3910);
    assert_eq!((state.rng.seed, state.rng.generation), (37443, 342));
    assert_eq!(state.items.iter().flatten().count(), 2);
    assert_eq!(state.enemy_bullets.active_count, 0);
}

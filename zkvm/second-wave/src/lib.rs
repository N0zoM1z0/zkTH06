#![no_std]
#![forbid(unsafe_code)]

//! Closed continuation over the first overlapping Stage-1 Sub0 group.
//!
//! The only external input per transition is the replay input mask. Enemy
//! timeline records, ECL motion, collisions, death RNG consumption, random
//! drops, Item motion, and the still-empty Enemy-bullet manager are derived.

use core::cmp::Ordering;

use zkth06_early_gameplay::{retail_early_gameplay_anchor, step_early_gameplay, EarlyGameplayError};
use zkth06_first_item::{
    from_first_collision, step_first_item, ActiveItem, FirstItemError, FirstItemState,
};
use zkth06_player_bullet_lifecycle::{
    ActiveBullet, FullSpeedTimer, LifecycleError, Vec2Bits, Vec3Bits, ACTIVE_SPRITE_FLAGS,
    ARCADE_HEIGHT_BITS, ARCADE_WIDTH_BITS, FULL_SPEED_BITS, HALF_BITS, PLAYER_POSITION_Z_BITS,
    STRAIGHT_SPRITE_SIZE_BITS,
};
use zkth06_player_bullets::{
    spawn_reimu_a, InitializedBullet, SpawnError, SpawnInput, BULLET_STATE_COLLIDED,
    BULLET_STATE_FIRED, BULLET_STATE_UNUSED, PLAYER_BULLET_SLOTS,
};
use zkth06_player_motion::pc24::{self, ArithmeticError};
use zkth06_player_shooting::{step_shooting_player, ShootingError};

pub const ANCHOR_GAME_FRAME: u32 = 249;
pub const PROFILE_LAST_GAME_FRAME: u32 = 350;
pub const SECOND_WAVE_ENEMY_SLOTS: usize = 5;
pub const TRACKED_ITEM_SLOTS: usize = 4;
pub const FIRST_SECOND_WAVE_SPAWN: u32 = 257;
pub const SECOND_WAVE_DEATH_FRAMES: [u32; 5] = [328, 331, 335, 343, 350];

const ZERO_BITS: u32 = 0;
const NEGATIVE_999_BITS: u32 = 0xc479_c000;
const INITIAL_ENEMY_Y_BITS: u32 = 0xc200_0000; // -32
const INITIAL_ENEMY_ANGLE_BITS: u32 = 0x3fc9_0fdb;
const INITIAL_AXIS_X_BITS: u32 = 0xb3bb_bd2e;
const TWO_BITS: u32 = 0x4000_0000;
const ANGULAR_VELOCITY_BITS: u32 = 0xbcc9_0fdb;
const ENEMY_HALF_HITBOX_BITS: u32 = 0x4160_0000;
const ENEMY_SPRITE_HALF_HEIGHT_BITS: u32 = 0x4170_0000;
const BULLET_HALF_SIZE_BITS: u32 = 0x40c0_0000;
const ONE_EIGHTH_BITS: u32 = 0x3e00_0000;
const COLLIDED_POSITION_Z_BITS: u32 = 0x3dcc_cccd;
const COLLIDED_SPRITE_FLAGS: u32 = 0x0000_1007;
const COLLIDED_ACTIVE_SPRITE: u16 = 1090;
const COLLIDED_ANM_FILE: u16 = 1120;
const COLLIDED_SPRITE_SIZE_BITS: u32 = 0x4180_0000;
const COLLISION_ANM_EXIT_TIMER: i32 = 30;
const ITEM_INITIAL_VELOCITY_Y_BITS: u32 = 0xc00c_cccd;
const ITEM_ACCELERATION_Y_BITS: u32 = 0x3cf5_c28f;
const ITEM_TERMINAL_VELOCITY_Y_BITS: u32 = 0x4040_0000;
const ITEM_HALF_SIZE_BITS: u32 = 0x4100_0000;
const PLAYER_ITEM_RADIUS_BITS: u32 = 0x4140_0000;
const ITEM_BOTTOM_BOUND_BITS: u32 = 0x43e8_0000;

// Exact x87 outputs of Sub0's sincosmul(angle, 2.0f), indexed by ECL time
// 41..=72. They are independently checked by the second-wave audit/vector.
const CURVED_AXIS: [Vec2Bits; 32] = [
    Vec2Bits { x: 0x3d49_0a7e, y: 0x3fff_ec43 },
    Vec2Bits { x: 0x3dc8_fb09, y: 0x3fff_b10f },
    Vec2Bits { x: 0x3e16_a8eb, y: 0x3fff_4e6e },
    Vec2Bits { x: 0x3e48_bd16, y: 0x3ffe_c46e },
    Vec2Bits { x: 0x3e7a_b24c, y: 0x3ffe_1324 },
    Vec2Bits { x: 0x3e96_406d, y: 0x3ffd_3aad },
    Vec2Bits { x: 0x3eaf_1088, y: 0x3ffc_3b29 },
    Vec2Bits { x: 0x3ec7_c5a5, y: 0x3ffb_14c0 },
    Vec2Bits { x: 0x3ee0_5bf3, y: 0x3ff9_c79f },
    Vec2Bits { x: 0x3ef8_cfa9, y: 0x3ff8_53fa },
    Vec2Bits { x: 0x3f08_8e80, y: 0x3ff6_ba0a },
    Vec2Bits { x: 0x3f14_a01d, y: 0x3ff4_fa0e },
    Vec2Bits { x: 0x3f20_9acf, y: 0x3ff3_144b },
    Vec2Bits { x: 0x3f2c_7cbc, y: 0x3ff1_090c },
    Vec2Bits { x: 0x3f38_4411, y: 0x3fee_d8a2 },
    Vec2Bits { x: 0x3f43_eefb, y: 0x3fec_8364 },
    Vec2Bits { x: 0x3f4f_7baf, y: 0x3fea_09ad },
    Vec2Bits { x: 0x3f5a_e864, y: 0x3fe7_6bde },
    Vec2Bits { x: 0x3f66_3357, y: 0x3fe4_aa60 },
    Vec2Bits { x: 0x3f71_5acb, y: 0x3fe1_c5a0 },
    Vec2Bits { x: 0x3f7c_5d07, y: 0x3fde_be0e },
    Vec2Bits { x: 0x3f83_9c2c, y: 0x3fdb_9424 },
    Vec2Bits { x: 0x3f88_f58a, y: 0x3fd8_485d },
    Vec2Bits { x: 0x3f8e_39c9, y: 0x3fd4_db3c },
    Vec2Bits { x: 0x3f93_681a, y: 0x3fd1_4d48 },
    Vec2Bits { x: 0x3f98_7fb0, y: 0x3fcd_9f0e },
    Vec2Bits { x: 0x3f9d_7fc2, y: 0x3fc9_d11e },
    Vec2Bits { x: 0x3fa2_678a, y: 0x3fc5_e40f },
    Vec2Bits { x: 0x3fa7_3648, y: 0x3fc1_d87d },
    Vec2Bits { x: 0x3fab_eb3c, y: 0x3fbd_af06 },
    Vec2Bits { x: 0x3fb0_85ad, y: 0x3fb9_684f },
    Vec2Bits { x: 0x3fb5_04e6, y: 0x3fb5_0500 },
];

const RANDOM_ITEM_TABLE_PREFIX: [u8; 3] = [0, 0, 1];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RngState {
    pub seed: u16,
    pub generation: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EnemyBulletPool {
    pub next_index: u16,
    pub bullet_count: u16,
    pub timer: FullSpeedTimer,
    pub active_count: u16,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SecondWaveEnemy {
    pub position: Vec3Bits,
    pub axis_speed: Vec2Bits,
    pub angle_bits: u32,
    pub angular_velocity_bits: u32,
    pub ecl_timer: FullSpeedTimer,
    pub life: i32,
    pub has_been_in_bounds: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SecondWaveState {
    pub first_item: FirstItemState,
    pub enemies: [Option<SecondWaveEnemy>; SECOND_WAVE_ENEMY_SLOTS],
    pub items: [Option<ActiveItem>; TRACKED_ITEM_SLOTS],
    pub rng: RngState,
    pub enemy_bullets: EnemyBulletPool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SecondWaveError {
    WrongAnchor(u32),
    ProfileEnded(u32),
    InvalidRetainedState,
    InvalidEnemy { slot: u8 },
    InvalidBullet { slot: u8 },
    InvalidItem { slot: u8 },
    ItemPoolExhausted,
    UnexpectedEnemyBullet,
    UnsupportedEclTime(i32),
    TimerOverflow,
    ScoreOverflow,
    LifeOverflow,
    RngOverflow,
    InputPrefixTooShort,
    Early(EarlyGameplayError),
    FirstItem(FirstItemError),
    Arithmetic(ArithmeticError),
    Lifecycle(LifecycleError),
    Shooting(ShootingError),
    Spawn(SpawnError),
}

impl From<ArithmeticError> for SecondWaveError {
    fn from(value: ArithmeticError) -> Self { Self::Arithmetic(value) }
}
impl From<EarlyGameplayError> for SecondWaveError {
    fn from(value: EarlyGameplayError) -> Self { Self::Early(value) }
}
impl From<FirstItemError> for SecondWaveError {
    fn from(value: FirstItemError) -> Self { Self::FirstItem(value) }
}
impl From<LifecycleError> for SecondWaveError {
    fn from(value: LifecycleError) -> Self { Self::Lifecycle(value) }
}
impl From<ShootingError> for SecondWaveError {
    fn from(value: ShootingError) -> Self { Self::Shooting(value) }
}
impl From<SpawnError> for SecondWaveError {
    fn from(value: SpawnError) -> Self { Self::Spawn(value) }
}

const fn reset_target() -> Vec3Bits {
    Vec3Bits { x: NEGATIVE_999_BITS, y: NEGATIVE_999_BITS, z: ZERO_BITS }
}

fn tick(timer: &mut FullSpeedTimer) -> Result<(), SecondWaveError> {
    timer.previous = timer.current;
    timer.current = timer.current.checked_add(1).ok_or(SecondWaveError::TimerOverflow)?;
    Ok(())
}

fn axis_for_time(time: i32) -> Result<Vec2Bits, SecondWaveError> {
    if (1..=40).contains(&time) {
        return Ok(Vec2Bits { x: INITIAL_AXIS_X_BITS, y: TWO_BITS });
    }
    let index = usize::try_from(time - 41).map_err(|_| SecondWaveError::UnsupportedEclTime(time))?;
    CURVED_AXIS.get(index).copied().ok_or(SecondWaveError::UnsupportedEclTime(time))
}

fn in_bounds(position: Vec3Bits, width: u32, height: u32) -> Result<bool, ArithmeticError> {
    let half_width = pc24::mul(width, HALF_BITS)?;
    let half_height = pc24::mul(height, HALF_BITS)?;
    Ok(pc24::compare(pc24::add(position.x, half_width)?, ZERO_BITS)? != Ordering::Less
        && pc24::compare(pc24::add(position.x, pc24::negate(half_width)?)?, ARCADE_WIDTH_BITS)?
            != Ordering::Greater
        && pc24::compare(pc24::add(position.y, half_height)?, ZERO_BITS)? != Ordering::Less
        && pc24::compare(pc24::add(position.y, pc24::negate(half_height)?)?, ARCADE_HEIGHT_BITS)?
            != Ordering::Greater)
}

fn initialized_bullet(value: InitializedBullet) -> ActiveBullet {
    ActiveBullet {
        position: value.position,
        size: value.size,
        velocity: value.velocity,
        sideways_motion_bits: value.sideways_motion_bits,
        unk_134: value.unk_134,
        age: FullSpeedTimer { previous: value.timer_previous, current: value.timer_current },
        damage: value.damage,
        bullet_type: value.bullet_type,
        unk_152: value.unk_152,
        spawn_position_idx: value.stored_spawn_position_idx,
        sprite_position: value.position,
        sprite_timer: FullSpeedTimer { previous: 0, current: 1 },
        sprite_flags: ACTIVE_SPRITE_FLAGS,
        sprite_active_index: value.requested_anm_script,
        sprite_anm_file_index: value.requested_anm_script,
        sprite_width_bits: STRAIGHT_SPRITE_SIZE_BITS,
        sprite_height_bits: STRAIGHT_SPRITE_SIZE_BITS,
    }
}

fn update_player_bullets(state: &mut SecondWaveState) -> Result<(), SecondWaveError> {
    for slot in 0..PLAYER_BULLET_SLOTS {
        let Some(mut bullet) = state.first_item.wave.player.bullets.slots[slot] else { continue };
        bullet.position.x = pc24::add(bullet.position.x, pc24::mul(bullet.velocity.x, FULL_SPEED_BITS)?)?;
        bullet.position.y = pc24::add(bullet.position.y, pc24::mul(bullet.velocity.y, FULL_SPEED_BITS)?)?;
        bullet.sprite_position = bullet.position;
        if !in_bounds(bullet.position, bullet.sprite_width_bits, bullet.sprite_height_bits)?
            || (state.first_item.wave.bullet_states[slot] == BULLET_STATE_COLLIDED
                && bullet.sprite_timer.current >= COLLISION_ANM_EXIT_TIMER)
        {
            state.first_item.wave.player.bullets.slots[slot] = None;
            state.first_item.wave.bullet_states[slot] = BULLET_STATE_UNUSED;
            continue;
        }
        tick(&mut bullet.sprite_timer)?;
        tick(&mut bullet.age)?;
        state.first_item.wave.player.bullets.slots[slot] = Some(bullet);
    }
    Ok(())
}

fn spawn_player_bullets(state: &mut SecondWaveState, timer: u8) -> Result<(), SecondWaveError> {
    let player = state.first_item.wave.player.shooting.enclosing.position;
    let output = spawn_reimu_a(SpawnInput {
        timer,
        current_power: state.first_item.current_power,
        player_position: Vec3Bits { x: player.x_bits, y: player.y_bits, z: PLAYER_POSITION_Z_BITS },
        orb_positions: [Vec3Bits::default(); 2],
        slot_states: state.first_item.wave.bullet_states,
        slot_carry: state.first_item.wave.player.bullets.carry,
    })?;
    for allocation in output.allocations.iter().copied().take(usize::from(output.allocation_count)) {
        let slot = usize::from(allocation.slot);
        if state.first_item.wave.player.bullets.slots[slot].is_some()
            || state.first_item.wave.bullet_states[slot] != BULLET_STATE_UNUSED
        {
            return Err(SecondWaveError::InvalidBullet { slot: allocation.slot });
        }
        state.first_item.wave.player.bullets.slots[slot] = Some(initialized_bullet(allocation));
        state.first_item.wave.bullet_states[slot] = BULLET_STATE_FIRED;
    }
    Ok(())
}

fn step_player(state: &mut SecondWaveState, input: u16) -> Result<(), SecondWaveError> {
    let (shooting, effects) = step_shooting_player(
        zkth06_player_bullet_lifecycle::reimu_a(),
        state.first_item.wave.player.shooting,
        input,
    )?;
    state.first_item.wave.player.shooting = shooting;
    update_player_bullets(state)?;
    if let Some(timer) = effects.spawn_bullets_timer { spawn_player_bullets(state, timer)?; }
    state.first_item.wave.last_enemy_hit = reset_target();
    Ok(())
}

fn timeline_spawn(frame: u32) -> Option<(usize, u32)> {
    match frame {
        257 => Some((0, 0x43a2_0000)),
        273 => Some((1, 0x439e_0000)),
        289 => Some((2, 0x439a_0000)),
        305 => Some((3, 0x4396_0000)),
        321 => Some((4, 0x4392_0000)),
        337 => Some((0, 0x438e_0000)),
        _ => None,
    }
}

fn spawn_timeline_enemy(state: &mut SecondWaveState, slot: usize, x: u32) -> Result<(), SecondWaveError> {
    if state.enemies[slot].is_some() { return Err(SecondWaveError::InvalidEnemy { slot: slot as u8 }); }
    state.enemies[slot] = Some(SecondWaveEnemy {
        position: Vec3Bits { x, y: INITIAL_ENEMY_Y_BITS, z: ZERO_BITS },
        axis_speed: axis_for_time(1)?,
        angle_bits: INITIAL_ENEMY_ANGLE_BITS,
        angular_velocity_bits: ZERO_BITS,
        ecl_timer: FullSpeedTimer { previous: 0, current: 1 },
        life: 32,
        has_been_in_bounds: false,
    });
    Ok(())
}

fn overlaps(bullet: ActiveBullet, enemy: Vec3Bits) -> Result<bool, ArithmeticError> {
    let enemy_left = pc24::add(enemy.x, pc24::negate(ENEMY_HALF_HITBOX_BITS)?)?;
    let enemy_right = pc24::add(enemy.x, ENEMY_HALF_HITBOX_BITS)?;
    let enemy_top = pc24::add(enemy.y, pc24::negate(ENEMY_HALF_HITBOX_BITS)?)?;
    let enemy_bottom = pc24::add(enemy.y, ENEMY_HALF_HITBOX_BITS)?;
    let bullet_left = pc24::add(bullet.position.x, pc24::negate(BULLET_HALF_SIZE_BITS)?)?;
    let bullet_right = pc24::add(bullet.position.x, BULLET_HALF_SIZE_BITS)?;
    let bullet_top = pc24::add(bullet.position.y, pc24::negate(BULLET_HALF_SIZE_BITS)?)?;
    let bullet_bottom = pc24::add(bullet.position.y, BULLET_HALF_SIZE_BITS)?;
    Ok(pc24::compare(bullet_top, enemy_bottom)? != Ordering::Greater
        && pc24::compare(bullet_left, enemy_right)? != Ordering::Greater
        && pc24::compare(bullet_bottom, enemy_top)? != Ordering::Less
        && pc24::compare(bullet_right, enemy_left)? != Ordering::Less)
}

fn collide_bullet(bullet: &mut ActiveBullet) -> Result<(), ArithmeticError> {
    bullet.position.z = COLLIDED_POSITION_Z_BITS;
    bullet.velocity.x = pc24::mul(bullet.velocity.x, ONE_EIGHTH_BITS)?;
    bullet.velocity.y = pc24::mul(bullet.velocity.y, ONE_EIGHTH_BITS)?;
    bullet.sprite_flags = COLLIDED_SPRITE_FLAGS;
    bullet.sprite_active_index = COLLIDED_ACTIVE_SPRITE;
    bullet.sprite_anm_file_index = COLLIDED_ANM_FILE;
    bullet.sprite_width_bits = COLLIDED_SPRITE_SIZE_BITS;
    bullet.sprite_height_bits = COLLIDED_SPRITE_SIZE_BITS;
    bullet.sprite_timer = FullSpeedTimer { previous: 0, current: 1 };
    Ok(())
}

fn calc_damage(state: &mut SecondWaveState, enemy: Vec3Bits) -> Result<i32, SecondWaveError> {
    let mut damage = 0_i32;
    for slot in 0..PLAYER_BULLET_SLOTS {
        if state.first_item.wave.bullet_states[slot] != BULLET_STATE_FIRED { continue; }
        let Some(mut bullet) = state.first_item.wave.player.bullets.slots[slot] else {
            return Err(SecondWaveError::InvalidBullet { slot: slot as u8 });
        };
        if !overlaps(bullet, enemy)? { continue; }
        damage = damage.checked_add(i32::from(bullet.damage)).ok_or(SecondWaveError::LifeOverflow)?;
        collide_bullet(&mut bullet)?;
        state.first_item.wave.player.bullets.slots[slot] = Some(bullet);
        state.first_item.wave.bullet_states[slot] = BULLET_STATE_COLLIDED;
    }
    Ok(damage)
}

fn advance_enemy(enemy: &mut SecondWaveEnemy) -> Result<(), SecondWaveError> {
    // These timeline records use opcode 2, which sets EnemyFlags::invertX.
    enemy.position.x = pc24::add(enemy.position.x, pc24::negate(enemy.axis_speed.x)?)?;
    enemy.position.y = pc24::add(enemy.position.y, enemy.axis_speed.y)?;
    let next = enemy.ecl_timer.current.checked_add(1).ok_or(SecondWaveError::TimerOverflow)?;
    if enemy.ecl_timer.current == 40 { enemy.angular_velocity_bits = ANGULAR_VELOCITY_BITS; }
    enemy.angle_bits = pc24::add(enemy.angle_bits, enemy.angular_velocity_bits)?;
    // The frame-328 slot reaches ECL time 73 and is destroyed later in this
    // same EnemyManager iteration. Its newly written axis is dead before the
    // next Move; the finite slice therefore does not need a trigonometric
    // witness for time 73.
    if next <= 72 {
        enemy.axis_speed = axis_for_time(next)?;
    } else if next != 73 {
        return Err(SecondWaveError::UnsupportedEclTime(next));
    }
    tick(&mut enemy.ecl_timer)?;
    Ok(())
}

fn rng_u16(rng: &mut RngState) -> Result<u16, SecondWaveError> {
    let a = (rng.seed ^ 0x9630).wrapping_sub(0x6553);
    rng.seed = (((a & 0xc000) >> 14).wrapping_add(a.wrapping_mul(4))) & 0xffff;
    rng.generation = rng.generation.checked_add(1).ok_or(SecondWaveError::RngOverflow)?;
    Ok(rng.seed)
}

fn consume_death_effect_rng(state: &mut SecondWaveState, random_drop: bool) -> Result<(), SecondWaveError> {
    let effects = if random_drop { 11 } else { 5 };
    // Every death effect executes one random-sprite opcode (one U16) and one
    // random-splash callback (two U32 = four U16) in the same calc frame.
    for _ in 0..effects * 5 { let _ = rng_u16(&mut state.rng)?; }
    Ok(())
}

fn allocate_item(state: &mut SecondWaveState, position: Vec3Bits, item_type: u8) -> Result<(), SecondWaveError> {
    let start = usize::from(state.first_item.item_next_index);
    let Some(slot) = (0..TRACKED_ITEM_SLOTS)
        .map(|offset| (start + offset) % TRACKED_ITEM_SLOTS)
        .find(|&slot| state.items[slot].is_none())
    else { return Err(SecondWaveError::ItemPoolExhausted) };
    state.first_item.item_next_index = ((slot + 1) % 511) as u16;
    state.items[slot] = Some(ActiveItem {
        current_position: position,
        start_position: Vec3Bits { x: ZERO_BITS, y: ITEM_INITIAL_VELOCITY_Y_BITS, z: ZERO_BITS },
        target_position: Vec3Bits::default(),
        timer: FullSpeedTimer { previous: -999, current: 0 },
        item_type,
        state: 0,
        unk_142: 1,
    });
    Ok(())
}

fn enemy_death(state: &mut SecondWaveState, position: Vec3Bits) -> Result<(), SecondWaveError> {
    state.first_item.wave.score = state.first_item.wave.score.checked_add(300).ok_or(SecondWaveError::ScoreOverflow)?;
    let random_drop = state.first_item.random_item_spawn_index.is_multiple_of(3);
    if random_drop {
        let index = usize::from(state.first_item.random_item_table_index);
        let item_type = *RANDOM_ITEM_TABLE_PREFIX.get(index).ok_or(SecondWaveError::InvalidRetainedState)?;
        allocate_item(state, position, item_type)?;
        state.first_item.random_item_table_index = state.first_item.random_item_table_index
            .checked_add(1).ok_or(SecondWaveError::InvalidRetainedState)?;
    }
    state.first_item.random_item_spawn_index = state.first_item.random_item_spawn_index
        .checked_add(1).ok_or(SecondWaveError::InvalidRetainedState)?;
    consume_death_effect_rng(state, random_drop)
}

fn update_enemies(state: &mut SecondWaveState) -> Result<(), SecondWaveError> {
    let frame = state.first_item.wave.player.shooting.enclosing.game_frame;
    if let Some((slot, x)) = timeline_spawn(frame) { spawn_timeline_enemy(state, slot, x)?; }
    for slot in 0..SECOND_WAVE_ENEMY_SLOTS {
        let Some(mut enemy) = state.enemies[slot] else { continue };
        advance_enemy(&mut enemy)?;
        if !enemy.has_been_in_bounds
            && pc24::compare(
                pc24::add(enemy.position.y, ENEMY_SPRITE_HALF_HEIGHT_BITS)?,
                ZERO_BITS,
            )? != Ordering::Less
        {
            enemy.has_been_in_bounds = true;
        }
        let damage = if enemy.has_been_in_bounds {
            calc_damage(state, enemy.position)?.min(70)
        } else {
            0
        };
        let damage_score = u32::try_from((damage / 5) * 10).map_err(|_| SecondWaveError::ScoreOverflow)?;
        state.first_item.wave.score = state.first_item.wave.score.checked_add(damage_score)
            .ok_or(SecondWaveError::ScoreOverflow)?;
        enemy.life = enemy.life.checked_sub(damage).ok_or(SecondWaveError::LifeOverflow)?;
        if enemy.has_been_in_bounds
            && pc24::compare(state.first_item.wave.last_enemy_hit.y, enemy.position.y)? == Ordering::Less
        {
            state.first_item.wave.last_enemy_hit = enemy.position;
        }
        if enemy.life <= 0 {
            enemy_death(state, enemy.position)?;
            state.enemies[slot] = None;
        } else {
            if enemy.ecl_timer.current > 72 {
                return Err(SecondWaveError::UnsupportedEclTime(enemy.ecl_timer.current));
            }
            state.enemies[slot] = Some(enemy);
        }
    }
    Ok(())
}

fn overlaps_player(item: Vec3Bits, player: Vec3Bits) -> Result<bool, ArithmeticError> {
    let item_left = pc24::add(item.x, pc24::negate(ITEM_HALF_SIZE_BITS)?)?;
    let item_right = pc24::add(item.x, ITEM_HALF_SIZE_BITS)?;
    let item_top = pc24::add(item.y, pc24::negate(ITEM_HALF_SIZE_BITS)?)?;
    let item_bottom = pc24::add(item.y, ITEM_HALF_SIZE_BITS)?;
    let player_left = pc24::add(player.x, pc24::negate(PLAYER_ITEM_RADIUS_BITS)?)?;
    let player_right = pc24::add(player.x, PLAYER_ITEM_RADIUS_BITS)?;
    let player_top = pc24::add(player.y, pc24::negate(PLAYER_ITEM_RADIUS_BITS)?)?;
    let player_bottom = pc24::add(player.y, PLAYER_ITEM_RADIUS_BITS)?;
    Ok(pc24::compare(player_left, item_right)? != Ordering::Greater
        && pc24::compare(player_right, item_left)? != Ordering::Less
        && pc24::compare(player_top, item_bottom)? != Ordering::Greater
        && pc24::compare(player_bottom, item_top)? != Ordering::Less)
}

fn update_items(state: &mut SecondWaveState) -> Result<(), SecondWaveError> {
    state.first_item.item_count = state.items.iter().flatten().count() as u16;
    let player_position = state.first_item.wave.player.shooting.enclosing.position;
    let player = Vec3Bits { x: player_position.x_bits, y: player_position.y_bits, z: PLAYER_POSITION_Z_BITS };
    for slot in 0..TRACKED_ITEM_SLOTS {
        let Some(mut item) = state.items[slot] else { continue };
        item.current_position.x = pc24::add(item.current_position.x, item.start_position.x)?;
        item.current_position.y = pc24::add(item.current_position.y, item.start_position.y)?;
        item.current_position.z = pc24::add(item.current_position.z, item.start_position.z)?;
        if pc24::compare(item.current_position.y, ITEM_BOTTOM_BOUND_BITS)? != Ordering::Less {
            return Err(SecondWaveError::InvalidItem { slot: slot as u8 });
        }
        if pc24::compare(item.start_position.y, ITEM_TERMINAL_VELOCITY_Y_BITS)? == Ordering::Less {
            item.start_position.y = pc24::add(item.start_position.y, ITEM_ACCELERATION_Y_BITS)?;
        } else { item.start_position.y = ITEM_TERMINAL_VELOCITY_Y_BITS; }
        if overlaps_player(item.current_position, player)? {
            return Err(SecondWaveError::InvalidItem { slot: slot as u8 });
        }
        tick(&mut item.timer)?;
        state.items[slot] = Some(item);
    }
    Ok(())
}

fn validate(state: &SecondWaveState) -> Result<(), SecondWaveError> {
    let frame = state.first_item.wave.player.shooting.enclosing.game_frame;
    if !(ANCHOR_GAME_FRAME..=PROFILE_LAST_GAME_FRAME).contains(&frame) {
        return Err(SecondWaveError::WrongAnchor(frame));
    }
    if state.first_item.item.is_some()
        || state.first_item.current_power != 1
        || state.first_item.subrank != 1
        || state.enemy_bullets.next_index != 0
        || state.enemy_bullets.bullet_count != 0
        || state.enemy_bullets.active_count != 0
        || state.enemy_bullets.timer.current != frame as i32
        || state.enemy_bullets.timer.previous != frame as i32 - 1
    {
        return Err(SecondWaveError::UnexpectedEnemyBullet);
    }
    for (slot, enemy) in state.enemies.iter().enumerate() {
        if let Some(enemy) = enemy {
            if enemy.life != 32
                || enemy.position.z != ZERO_BITS
                || enemy.ecl_timer.current < 2
                || enemy.ecl_timer.previous != enemy.ecl_timer.current - 1
                || enemy.axis_speed != axis_for_time(enemy.ecl_timer.current)?
                || enemy.angular_velocity_bits
                    != if enemy.ecl_timer.current <= 40 { ZERO_BITS } else { ANGULAR_VELOCITY_BITS }
                || enemy.has_been_in_bounds != (enemy.ecl_timer.current >= 10)
            {
                return Err(SecondWaveError::InvalidEnemy { slot: slot as u8 });
            }
        }
    }
    for (slot, item) in state.items.iter().enumerate() {
        if let Some(item) = item {
            if item.state != 0 || item.unk_142 != 1 || item.target_position != Vec3Bits::default()
                || item.timer.current <= 0 || item.timer.previous != item.timer.current - 1
            {
                return Err(SecondWaveError::InvalidItem { slot: slot as u8 });
            }
        }
    }
    Ok(())
}

/// Converts the fully derived first-Item state. RNG and the Enemy-bullet
/// manager values are fixed retail/reference constants at that boundary, not
/// unconstrained witness fields.
pub fn from_first_item(first_item: FirstItemState) -> Result<SecondWaveState, SecondWaveError> {
    let frame = first_item.wave.player.shooting.enclosing.game_frame;
    if frame != ANCHOR_GAME_FRAME || first_item.item.is_some() || first_item.current_power != 1
        || first_item.subrank != 1 || first_item.random_item_spawn_index != 6
        || first_item.random_item_table_index != 1 || first_item.item_next_index != 1
    {
        return Err(SecondWaveError::WrongAnchor(frame));
    }
    let result = SecondWaveState {
        first_item,
        enemies: [None; SECOND_WAVE_ENEMY_SLOTS],
        items: [None; TRACKED_ITEM_SLOTS],
        rng: RngState { seed: 41015, generation: 157 },
        enemy_bullets: EnemyBulletPool {
            next_index: 0,
            bullet_count: 0,
            timer: FullSpeedTimer { previous: 248, current: 249 },
            active_count: 0,
        },
    };
    validate(&result)?;
    Ok(result)
}

/// Replays the already-closed kernels from their fixed frame-1 retail anchor
/// to frame 249. This avoids introducing a serialized intermediate state as a
/// fresh witness in the second-wave proof.
pub fn derive_second_wave_anchor(inputs: &[u16]) -> Result<SecondWaveState, SecondWaveError> {
    if inputs.len() < ANCHOR_GAME_FRAME as usize {
        return Err(SecondWaveError::InputPrefixTooShort);
    }
    let mut early = retail_early_gameplay_anchor()?;
    for game_frame in 2..=208_u32 {
        early = step_early_gameplay(early, inputs[game_frame as usize - 1])?;
    }
    let mut first_item = from_first_collision(early)?;
    for game_frame in 209..=ANCHOR_GAME_FRAME {
        first_item = step_first_item(first_item, inputs[game_frame as usize - 1])?;
    }
    from_first_item(first_item)
}

/// Advances one canonical replay frame and fails closed at frame 350.
pub fn step_second_wave(mut state: SecondWaveState, input: u16) -> Result<SecondWaveState, SecondWaveError> {
    let prior = state.first_item.wave.player.shooting.enclosing.game_frame;
    if prior >= PROFILE_LAST_GAME_FRAME { return Err(SecondWaveError::ProfileEnded(prior)); }
    validate(&state)?;
    step_player(&mut state, input)?;
    update_enemies(&mut state)?;
    update_items(&mut state)?;
    tick(&mut state.enemy_bullets.timer)?;
    validate(&state)?;
    Ok(state)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pinned_rng_death_footprints_match_retail() {
        let mut rng = RngState { seed: 41015, generation: 157 };
        for _ in 0..55 { rng_u16(&mut rng).unwrap(); }
        assert_eq!(rng, RngState { seed: 25806, generation: 212 });
        for _ in 0..25 { rng_u16(&mut rng).unwrap(); }
        assert_eq!(rng, RngState { seed: 22632, generation: 237 });
        for _ in 0..25 { rng_u16(&mut rng).unwrap(); }
        assert_eq!(rng, RngState { seed: 1107, generation: 262 });
        for _ in 0..55 { rng_u16(&mut rng).unwrap(); }
        assert_eq!(rng, RngState { seed: 14583, generation: 317 });
        for _ in 0..25 { rng_u16(&mut rng).unwrap(); }
        assert_eq!(rng, RngState { seed: 37443, generation: 342 });
    }
}

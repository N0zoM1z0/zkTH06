#![no_std]
#![forbid(unsafe_code)]

//! Closed continuation through the first death-Item collection.
//!
//! The fixed route starts from the frame-208 state derived by the enclosing
//! gameplay kernel. Enemy deaths advance the deterministic random-drop cursor;
//! its third death selects the first random-item-table entry and spawns one
//! small-power Item. The Item's movement, Player AABB collision, and retained
//! score/power/subrank feedback are then derived through frame 249.

use core::cmp::Ordering;

use zkth06_early_gameplay::EarlyGameplayState;
use zkth06_first_wave::{
    from_first_collision as from_first_wave_collision, step_first_wave, FirstWaveError,
    FirstWaveState, ANCHOR_GAME_FRAME, PROFILE_LAST_GAME_FRAME as FIRST_WAVE_LAST_GAME_FRAME,
};
use zkth06_player_bullet_lifecycle::{
    ActiveBullet, FullSpeedTimer, LifecycleError, Vec2Bits, Vec3Bits, ACTIVE_SPRITE_FLAGS,
    ARCADE_HEIGHT_BITS, ARCADE_WIDTH_BITS, FIXED_POWER, FULL_SPEED_BITS, HALF_BITS,
    PLAYER_POSITION_Z_BITS, STRAIGHT_DAMAGE, STRAIGHT_DIRECTION_BITS, STRAIGHT_SIZE_BITS,
    STRAIGHT_SPEED_BITS, STRAIGHT_SPRITE_SIZE_BITS, STRAIGHT_VELOCITY_X_BITS,
    STRAIGHT_VELOCITY_Y_BITS,
};
use zkth06_player_bullets::{
    spawn_reimu_a, InitializedBullet, SpawnError, SpawnInput, BULLET_STATE_COLLIDED,
    BULLET_STATE_FIRED, BULLET_STATE_UNUSED, BULLET_Z_BITS, ONE_BITS, PLAYER_BULLET_ANM,
    PLAYER_BULLET_SLOTS,
};
use zkth06_player_motion::pc24::{self, ArithmeticError};
use zkth06_player_shooting::{step_shooting_player, ShootingError};

pub const PROFILE_LAST_GAME_FRAME: u32 = 249;
pub const ITEM_SPAWN_GAME_FRAME: u32 = 219;
pub const ITEM_COLLECTION_GAME_FRAME: u32 = 249;

const ZERO_BITS: u32 = 0;
const NEGATIVE_999_BITS: u32 = 0xc479_c000;
const ITEM_INITIAL_VELOCITY_Y_BITS: u32 = 0xc00c_cccd;
const ITEM_ACCELERATION_Y_BITS: u32 = 0x3cf5_c28f;
const ITEM_TERMINAL_VELOCITY_Y_BITS: u32 = 0x4040_0000;
const ITEM_HALF_SIZE_BITS: u32 = 0x4100_0000;
const PLAYER_ITEM_RADIUS_BITS: u32 = 0x4140_0000;
const ITEM_BOTTOM_BOUND_BITS: u32 = 0x43e8_0000;
const COLLIDED_POSITION_Z_BITS: u32 = 0x3dcc_cccd;
const COLLIDED_SPRITE_FLAGS: u32 = 0x0000_1007;
const COLLIDED_ACTIVE_SPRITE: u16 = 1090;
const COLLIDED_ANM_FILE: u16 = 1120;
const COLLIDED_SPRITE_SIZE_BITS: u32 = 0x4180_0000;
const COLLISION_ANM_EXIT_TIMER: i32 = 30;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActiveItem {
    pub current_position: Vec3Bits,
    pub start_position: Vec3Bits,
    pub target_position: Vec3Bits,
    pub timer: FullSpeedTimer,
    pub item_type: u8,
    pub state: u8,
    pub unk_142: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FirstItemState {
    pub wave: FirstWaveState,
    pub item: Option<ActiveItem>,
    pub item_next_index: u16,
    pub item_count: u16,
    pub random_item_spawn_index: u8,
    pub random_item_table_index: u8,
    pub current_power: u16,
    pub subrank: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FirstItemError {
    WrongAnchor(u32),
    ProfileEnded(u32),
    InvalidBullet { slot: u8 },
    InvalidItem,
    InvalidItemAllocator,
    InvalidRandomDropState,
    InvalidRetainedState,
    MultipleEnemyDeaths,
    TimerOverflow,
    ScoreOverflow,
    PowerOverflow,
    SubrankOverflow,
    FirstWave(FirstWaveError),
    Lifecycle(LifecycleError),
    Shooting(ShootingError),
    Spawn(SpawnError),
    Arithmetic(ArithmeticError),
}

impl From<FirstWaveError> for FirstItemError {
    fn from(value: FirstWaveError) -> Self {
        Self::FirstWave(value)
    }
}

impl From<LifecycleError> for FirstItemError {
    fn from(value: LifecycleError) -> Self {
        Self::Lifecycle(value)
    }
}

impl From<ShootingError> for FirstItemError {
    fn from(value: ShootingError) -> Self {
        Self::Shooting(value)
    }
}

impl From<SpawnError> for FirstItemError {
    fn from(value: SpawnError) -> Self {
        Self::Spawn(value)
    }
}

impl From<ArithmeticError> for FirstItemError {
    fn from(value: ArithmeticError) -> Self {
        Self::Arithmetic(value)
    }
}

const fn reset_target() -> Vec3Bits {
    Vec3Bits {
        x: NEGATIVE_999_BITS,
        y: NEGATIVE_999_BITS,
        z: ZERO_BITS,
    }
}

fn expected_random_spawn_index(frame: u32) -> u8 {
    match frame {
        ANCHOR_GAME_FRAME..=212 => 2,
        213..=218 => 3,
        219..=223 => 4,
        224..=228 => 5,
        _ => 6,
    }
}

fn expected_item(frame: u32) -> bool {
    (ITEM_SPAWN_GAME_FRAME..ITEM_COLLECTION_GAME_FRAME).contains(&frame)
}

fn expected_score(frame: u32) -> u32 {
    match frame {
        ANCHOR_GAME_FRAME..=212 => 390,
        213..=218 => 780,
        219..=223 => 1170,
        224..=228 => 1560,
        229..=248 => 1950,
        _ => 1960,
    }
}

fn validate_timer(timer: FullSpeedTimer) -> bool {
    timer.current > 0 && timer.previous == timer.current - 1
}

fn validate_bullet_age(timer: FullSpeedTimer) -> bool {
    (timer.previous == -999 && timer.current == 0) || validate_timer(timer)
}

fn validate_item(state: &FirstItemState) -> Result<(), FirstItemError> {
    let frame = state.wave.player.shooting.enclosing.game_frame;
    if state.item.is_some() != expected_item(frame) {
        return Err(FirstItemError::InvalidItem);
    }
    if let Some(item) = state.item {
        if item.current_position.x != 0x42aa_4cd0
            || item.current_position.z != ZERO_BITS
            || item.start_position.x != ZERO_BITS
            || item.start_position.z != ZERO_BITS
            || item.target_position != Vec3Bits::default()
            || !validate_timer(item.timer)
            || item.timer.current != i32::try_from(frame - 218).unwrap_or(i32::MAX)
            || item.item_type != 0
            || item.state != 0
            || item.unk_142 != 1
        {
            return Err(FirstItemError::InvalidItem);
        }
    }
    let spawned = frame >= ITEM_SPAWN_GAME_FRAME;
    if state.item_next_index != u16::from(spawned) || state.item_count != u16::from(spawned) {
        return Err(FirstItemError::InvalidItemAllocator);
    }
    if state.random_item_spawn_index != expected_random_spawn_index(frame)
        || state.random_item_table_index != u8::from(spawned)
    {
        return Err(FirstItemError::InvalidRandomDropState);
    }
    let collected = frame >= ITEM_COLLECTION_GAME_FRAME;
    if state.current_power != u16::from(collected)
        || state.subrank != i32::from(collected)
        || state.wave.score != expected_score(frame)
    {
        return Err(FirstItemError::InvalidRetainedState);
    }
    Ok(())
}

fn validate_continuation_bullets(state: &FirstItemState) -> Result<(), FirstItemError> {
    let frame = state.wave.player.shooting.enclosing.game_frame;
    if frame <= FIRST_WAVE_LAST_GAME_FRAME {
        return Ok(());
    }
    if state.wave.enemies.iter().any(Option::is_some) {
        return Err(FirstItemError::InvalidRetainedState);
    }
    for slot in 0..PLAYER_BULLET_SLOTS {
        let bullet_state = state.wave.bullet_states[slot];
        let Some(bullet) = state.wave.player.bullets.slots[slot] else {
            if bullet_state != BULLET_STATE_UNUSED {
                return Err(FirstItemError::InvalidBullet { slot: slot as u8 });
            }
            continue;
        };
        let carry = state.wave.player.bullets.carry[slot];
        let common = bullet.bullet_type == 0
            && bullet.damage == STRAIGHT_DAMAGE
            && bullet.size
                == Vec3Bits {
                    x: STRAIGHT_SIZE_BITS,
                    y: STRAIGHT_SIZE_BITS,
                    z: ONE_BITS,
                }
            && bullet.sideways_motion_bits == carry.sideways_motion_bits
            && bullet.unk_134
                == Vec3Bits {
                    x: carry.unk_134_x_bits,
                    y: STRAIGHT_SPEED_BITS,
                    z: STRAIGHT_DIRECTION_BITS,
                }
            && bullet.unk_152 == carry.unk_152
            && bullet.spawn_position_idx == carry.stored_spawn_position_idx
            && validate_bullet_age(bullet.age)
            && validate_timer(bullet.sprite_timer);
        let specific = match bullet_state {
            BULLET_STATE_FIRED => {
                bullet.position.z == BULLET_Z_BITS
                    && bullet.velocity
                        == Vec2Bits {
                            x: STRAIGHT_VELOCITY_X_BITS,
                            y: STRAIGHT_VELOCITY_Y_BITS,
                        }
                    && bullet.sprite_position == bullet.position
                    && bullet.sprite_flags == ACTIVE_SPRITE_FLAGS
                    && bullet.sprite_active_index == PLAYER_BULLET_ANM
                    && bullet.sprite_anm_file_index == PLAYER_BULLET_ANM
                    && bullet.sprite_width_bits == STRAIGHT_SPRITE_SIZE_BITS
                    && bullet.sprite_height_bits == STRAIGHT_SPRITE_SIZE_BITS
            }
            BULLET_STATE_COLLIDED => {
                bullet.position.z == COLLIDED_POSITION_Z_BITS
                    && bullet.velocity
                        == Vec2Bits {
                            x: 0xb38c_cde2,
                            y: 0xbfc0_0000,
                        }
                    && bullet.sprite_position == bullet.position
                    && bullet.sprite_flags == COLLIDED_SPRITE_FLAGS
                    && bullet.sprite_active_index == COLLIDED_ACTIVE_SPRITE
                    && bullet.sprite_anm_file_index == COLLIDED_ANM_FILE
                    && bullet.sprite_width_bits == COLLIDED_SPRITE_SIZE_BITS
                    && bullet.sprite_height_bits == COLLIDED_SPRITE_SIZE_BITS
                    && bullet.sprite_timer.current <= COLLISION_ANM_EXIT_TIMER
            }
            _ => false,
        };
        if !common || !specific {
            return Err(FirstItemError::InvalidBullet { slot: slot as u8 });
        }
    }
    Ok(())
}

fn validate_state(state: &FirstItemState) -> Result<(), FirstItemError> {
    let frame = state.wave.player.shooting.enclosing.game_frame;
    if !(ANCHOR_GAME_FRAME..=PROFILE_LAST_GAME_FRAME).contains(&frame) {
        return Err(FirstItemError::WrongAnchor(frame));
    }
    validate_item(state)?;
    validate_continuation_bullets(state)
}

/// Converts the already-derived first collision. The first death has advanced
/// the random-drop cadence once, but no Item has spawned.
pub fn from_first_collision(state: EarlyGameplayState) -> Result<FirstItemState, FirstItemError> {
    let wave = from_first_wave_collision(state)?;
    let result = FirstItemState {
        wave,
        item: None,
        item_next_index: 0,
        item_count: 0,
        random_item_spawn_index: 2,
        random_item_table_index: 0,
        current_power: 0,
        subrank: 0,
    };
    validate_state(&result)?;
    Ok(result)
}

fn in_bounds(position: Vec3Bits, width: u32, height: u32) -> Result<bool, ArithmeticError> {
    let half_width = pc24::mul(width, HALF_BITS)?;
    let half_height = pc24::mul(height, HALF_BITS)?;
    if pc24::compare(pc24::add(position.x, half_width)?, ZERO_BITS)? == Ordering::Less {
        return Ok(false);
    }
    if pc24::compare(
        pc24::add(position.x, pc24::negate(half_width)?)?,
        ARCADE_WIDTH_BITS,
    )? == Ordering::Greater
    {
        return Ok(false);
    }
    if pc24::compare(pc24::add(position.y, half_height)?, ZERO_BITS)? == Ordering::Less {
        return Ok(false);
    }
    if pc24::compare(
        pc24::add(position.y, pc24::negate(half_height)?)?,
        ARCADE_HEIGHT_BITS,
    )? == Ordering::Greater
    {
        return Ok(false);
    }
    Ok(true)
}

fn tick_timer(timer: &mut FullSpeedTimer) -> Result<(), FirstItemError> {
    timer.previous = timer.current;
    timer.current = timer
        .current
        .checked_add(1)
        .ok_or(FirstItemError::TimerOverflow)?;
    Ok(())
}

fn update_bullets(state: &mut FirstItemState) -> Result<(), FirstItemError> {
    for slot in 0..PLAYER_BULLET_SLOTS {
        let Some(mut bullet) = state.wave.player.bullets.slots[slot] else {
            continue;
        };
        bullet.position.x = pc24::add(
            bullet.position.x,
            pc24::mul(bullet.velocity.x, FULL_SPEED_BITS)?,
        )?;
        bullet.position.y = pc24::add(
            bullet.position.y,
            pc24::mul(bullet.velocity.y, FULL_SPEED_BITS)?,
        )?;
        bullet.sprite_position = bullet.position;
        if !in_bounds(
            bullet.position,
            bullet.sprite_width_bits,
            bullet.sprite_height_bits,
        )? || (state.wave.bullet_states[slot] == BULLET_STATE_COLLIDED
            && bullet.sprite_timer.current >= COLLISION_ANM_EXIT_TIMER)
        {
            state.wave.player.bullets.slots[slot] = None;
            state.wave.bullet_states[slot] = BULLET_STATE_UNUSED;
            continue;
        }
        tick_timer(&mut bullet.sprite_timer)?;
        tick_timer(&mut bullet.age)?;
        state.wave.player.bullets.slots[slot] = Some(bullet);
    }
    Ok(())
}

fn initialized_bullet(value: InitializedBullet) -> ActiveBullet {
    ActiveBullet {
        position: value.position,
        size: value.size,
        velocity: value.velocity,
        sideways_motion_bits: value.sideways_motion_bits,
        unk_134: value.unk_134,
        age: FullSpeedTimer {
            previous: value.timer_previous,
            current: value.timer_current,
        },
        damage: value.damage,
        bullet_type: value.bullet_type,
        unk_152: value.unk_152,
        spawn_position_idx: value.stored_spawn_position_idx,
        sprite_position: value.position,
        sprite_timer: FullSpeedTimer {
            previous: 0,
            current: 1,
        },
        sprite_flags: ACTIVE_SPRITE_FLAGS,
        sprite_active_index: value.requested_anm_script,
        sprite_anm_file_index: value.requested_anm_script,
        sprite_width_bits: STRAIGHT_SPRITE_SIZE_BITS,
        sprite_height_bits: STRAIGHT_SPRITE_SIZE_BITS,
    }
}

fn spawn_bullets(state: &mut FirstItemState, timer: u8) -> Result<(), FirstItemError> {
    let output = spawn_reimu_a(SpawnInput {
        timer,
        current_power: FIXED_POWER,
        player_position: Vec3Bits {
            x: state.wave.player.shooting.enclosing.position.x_bits,
            y: state.wave.player.shooting.enclosing.position.y_bits,
            z: PLAYER_POSITION_Z_BITS,
        },
        orb_positions: [Vec3Bits::default(); 2],
        slot_states: state.wave.bullet_states,
        slot_carry: state.wave.player.bullets.carry,
    })?;
    for allocation in output
        .allocations
        .iter()
        .copied()
        .take(usize::from(output.allocation_count))
    {
        let slot = usize::from(allocation.slot);
        if state.wave.player.bullets.slots[slot].is_some()
            || state.wave.bullet_states[slot] != BULLET_STATE_UNUSED
        {
            return Err(FirstItemError::InvalidBullet {
                slot: allocation.slot,
            });
        }
        state.wave.player.bullets.slots[slot] = Some(initialized_bullet(allocation));
        state.wave.bullet_states[slot] = BULLET_STATE_FIRED;
    }
    Ok(())
}

fn step_player_after_wave(
    mut state: FirstItemState,
    input: u16,
) -> Result<FirstItemState, FirstItemError> {
    let (shooting, effects) = step_shooting_player(
        zkth06_player_bullet_lifecycle::reimu_a(),
        state.wave.player.shooting,
        input,
    )?;
    state.wave.player.shooting = shooting;
    update_bullets(&mut state)?;
    if let Some(timer) = effects.spawn_bullets_timer {
        spawn_bullets(&mut state, timer)?;
    }
    state.wave.last_enemy_hit = reset_target();
    Ok(state)
}

fn spawn_random_drop(state: &mut FirstItemState, position: Vec3Bits) -> Result<(), FirstItemError> {
    if state.random_item_spawn_index.is_multiple_of(3) {
        if state.item.is_some() || state.item_next_index != 0 || state.random_item_table_index != 0
        {
            return Err(FirstItemError::InvalidItemAllocator);
        }
        state.item = Some(ActiveItem {
            current_position: position,
            start_position: Vec3Bits {
                x: ZERO_BITS,
                y: ITEM_INITIAL_VELOCITY_Y_BITS,
                z: ZERO_BITS,
            },
            target_position: Vec3Bits::default(),
            timer: FullSpeedTimer {
                previous: -999,
                current: 0,
            },
            item_type: 0,
            state: 0,
            unk_142: 1,
        });
        state.item_next_index = 1;
        state.random_item_table_index = 1;
    }
    state.random_item_spawn_index = state
        .random_item_spawn_index
        .checked_add(1)
        .ok_or(FirstItemError::InvalidRandomDropState)?;
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

fn update_item(state: &mut FirstItemState) -> Result<(), FirstItemError> {
    state.item_count = u16::from(state.item.is_some());
    let Some(mut item) = state.item else {
        return Ok(());
    };
    item.current_position.x = pc24::add(item.current_position.x, item.start_position.x)?;
    item.current_position.y = pc24::add(item.current_position.y, item.start_position.y)?;
    item.current_position.z = pc24::add(item.current_position.z, item.start_position.z)?;
    if pc24::compare(item.current_position.y, ITEM_BOTTOM_BOUND_BITS)? != Ordering::Less {
        return Err(FirstItemError::InvalidItem);
    }
    if pc24::compare(item.start_position.y, ITEM_TERMINAL_VELOCITY_Y_BITS)? == Ordering::Less {
        item.start_position.y = pc24::add(item.start_position.y, ITEM_ACCELERATION_Y_BITS)?;
    } else {
        item.start_position.y = ITEM_TERMINAL_VELOCITY_Y_BITS;
    }
    let player = Vec3Bits {
        x: state.wave.player.shooting.enclosing.position.x_bits,
        y: state.wave.player.shooting.enclosing.position.y_bits,
        z: PLAYER_POSITION_Z_BITS,
    };
    if overlaps_player(item.current_position, player)? {
        state.wave.score = state
            .wave
            .score
            .checked_add(10)
            .ok_or(FirstItemError::ScoreOverflow)?;
        state.current_power = state
            .current_power
            .checked_add(1)
            .ok_or(FirstItemError::PowerOverflow)?;
        state.subrank = state
            .subrank
            .checked_add(1)
            .ok_or(FirstItemError::SubrankOverflow)?;
        state.item = None;
        return Ok(());
    }
    tick_timer(&mut item.timer)?;
    state.item = Some(item);
    Ok(())
}

/// Advances one replay frame through the first Item feedback boundary.
pub fn step_first_item(
    mut state: FirstItemState,
    input: u16,
) -> Result<FirstItemState, FirstItemError> {
    let prior_frame = state.wave.player.shooting.enclosing.game_frame;
    if prior_frame >= PROFILE_LAST_GAME_FRAME {
        return Err(FirstItemError::ProfileEnded(prior_frame));
    }
    validate_state(&state)?;
    let prior_enemies = state.wave.enemies.iter().flatten().count();
    if prior_frame < FIRST_WAVE_LAST_GAME_FRAME {
        state.wave = step_first_wave(state.wave, input)?;
    } else {
        state = step_player_after_wave(state, input)?;
    }
    let next_enemies = state.wave.enemies.iter().flatten().count();
    let deaths = prior_enemies
        .checked_sub(next_enemies)
        .ok_or(FirstItemError::InvalidRetainedState)?;
    match deaths {
        0 => {}
        1 => {
            let position = state.wave.last_enemy_hit;
            spawn_random_drop(&mut state, position)?;
        }
        _ => return Err(FirstItemError::MultipleEnemyDeaths),
    }
    update_item(&mut state)?;
    validate_state(&state)?;
    Ok(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use zkth06_early_gameplay::retail_early_gameplay_anchor;

    #[test]
    fn conversion_rejects_a_state_before_the_first_collision() {
        let early = retail_early_gameplay_anchor().unwrap();
        assert_eq!(
            from_first_collision(early),
            Err(FirstItemError::FirstWave(FirstWaveError::WrongAnchor(1)))
        );
    }
}

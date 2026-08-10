#![no_std]
#![forbid(unsafe_code)]

//! Enclosing Reimu-A Player/bullet transition before the first Enemy hit.
//!
//! The fixed anchor contains the complete empty 80-slot pool at gameplay
//! frame 1. Each step derives Player motion and shooting cadence, advances all
//! existing rank-1 straight bullets, reclaims out-of-bounds slots, advances
//! the selected nonterminating ANM/timers, and applies `SpawnBullets`. Enemy
//! collision is deliberately not an input: this profile must stop before the
//! first frame whose EnemyManager phase mutates a Player bullet.

use core::cmp::Ordering;

use zkth06_player_bullets::{
    spawn_reimu_a, InitializedBullet, SlotCarry, SpawnError, SpawnInput, BULLET_STATE_FIRED,
    PLAYER_BULLET_ANM, PLAYER_BULLET_SLOTS,
};
pub use zkth06_player_bullets::{Vec2Bits, Vec3Bits};
use zkth06_player_motion::enclosing::{PlayerConfig, CHARACTER_REIMU, SHOT_TYPE_A};
use zkth06_player_motion::pc24::{self, ArithmeticError};
use zkth06_player_shooting::{
    retail_shooting_anchor_state, step_shooting_player, ShootingError, ShootingPlayerState,
};

pub const PROFILE_LAST_GAME_FRAME: u32 = 207;
pub const FIXED_POWER: u16 = 0;
pub const PLAYER_POSITION_Z_BITS: u32 = 0x3efa_e148;
pub const FULL_SPEED_BITS: u32 = 0x3f80_0000;
pub const HALF_BITS: u32 = 0x3f00_0000;
pub const ARCADE_WIDTH_BITS: u32 = 0x43c0_0000;
pub const ARCADE_HEIGHT_BITS: u32 = 0x43e0_0000;
pub const STRAIGHT_DAMAGE: i16 = 48;
pub const STRAIGHT_SIZE_BITS: u32 = 0x4140_0000;
pub const STRAIGHT_VELOCITY_X_BITS: u32 = 0xb50c_cde2;
pub const STRAIGHT_VELOCITY_Y_BITS: u32 = 0xc140_0000;
pub const STRAIGHT_SPEED_BITS: u32 = 0x4140_0000;
pub const STRAIGHT_DIRECTION_BITS: u32 = 0xbfc9_0fdb;
pub const STRAIGHT_SPRITE_SIZE_BITS: u32 = 0x4160_0000;
pub const ACTIVE_SPRITE_FLAGS: u32 = 0x0000_1003;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FullSpeedTimer {
    pub previous: i32,
    pub current: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActiveBullet {
    pub position: Vec3Bits,
    pub size: Vec3Bits,
    pub velocity: Vec2Bits,
    pub sideways_motion_bits: u32,
    pub unk_134: Vec3Bits,
    pub age: FullSpeedTimer,
    pub damage: i16,
    pub bullet_type: u8,
    pub unk_152: i16,
    pub spawn_position_idx: i16,
    pub sprite_position: Vec3Bits,
    pub sprite_timer: FullSpeedTimer,
    pub sprite_flags: u32,
    pub sprite_active_index: u16,
    pub sprite_anm_file_index: u16,
    pub sprite_width_bits: u32,
    pub sprite_height_bits: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BulletPool {
    pub slots: [Option<ActiveBullet>; PLAYER_BULLET_SLOTS],
    pub carry: [SlotCarry; PLAYER_BULLET_SLOTS],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PlayerBulletLifecycleState {
    pub shooting: ShootingPlayerState,
    pub bullets: BulletPool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LifecycleError {
    WrongRoute(PlayerConfig),
    ProfileEnded(u32),
    Shooting(ShootingError),
    Spawn(SpawnError),
    Arithmetic(ArithmeticError),
    InvalidBullet { slot: u8 },
    TimerOverflow { slot: u8 },
}

impl From<ShootingError> for LifecycleError {
    fn from(value: ShootingError) -> Self {
        Self::Shooting(value)
    }
}

impl From<SpawnError> for LifecycleError {
    fn from(value: SpawnError) -> Self {
        Self::Spawn(value)
    }
}

impl From<ArithmeticError> for LifecycleError {
    fn from(value: ArithmeticError) -> Self {
        Self::Arithmetic(value)
    }
}

pub const fn reimu_a() -> PlayerConfig {
    PlayerConfig {
        character: CHARACTER_REIMU,
        shot_type: SHOT_TYPE_A,
    }
}

/// Fixed post-calc frame-1 anchor. No bullet state is witness supplied.
pub fn retail_lifecycle_anchor_state(
    config: PlayerConfig,
) -> Result<PlayerBulletLifecycleState, LifecycleError> {
    if config != reimu_a() {
        return Err(LifecycleError::WrongRoute(config));
    }
    Ok(PlayerBulletLifecycleState {
        shooting: retail_shooting_anchor_state(config)?,
        bullets: BulletPool {
            slots: [None; PLAYER_BULLET_SLOTS],
            carry: [SlotCarry::default(); PLAYER_BULLET_SLOTS],
        },
    })
}

fn validate_timer(timer: FullSpeedTimer, allow_popup: bool) -> bool {
    (allow_popup && timer.previous == -999 && timer.current == 0)
        || (timer.current > 0 && timer.previous == timer.current - 1)
}

fn validate_bullet(
    slot: usize,
    bullet: ActiveBullet,
    carry: SlotCarry,
) -> Result<(), LifecycleError> {
    let valid = bullet.bullet_type == 0
        && bullet.damage == STRAIGHT_DAMAGE
        && bullet.position.z == zkth06_player_bullets::BULLET_Z_BITS
        && bullet.size
            == Vec3Bits {
                x: STRAIGHT_SIZE_BITS,
                y: STRAIGHT_SIZE_BITS,
                z: zkth06_player_bullets::ONE_BITS,
            }
        && bullet.velocity
            == Vec2Bits {
                x: STRAIGHT_VELOCITY_X_BITS,
                y: STRAIGHT_VELOCITY_Y_BITS,
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
        && bullet.sprite_position == bullet.position
        && bullet.sprite_flags == ACTIVE_SPRITE_FLAGS
        && bullet.sprite_active_index == PLAYER_BULLET_ANM
        && bullet.sprite_anm_file_index == PLAYER_BULLET_ANM
        && bullet.sprite_width_bits == STRAIGHT_SPRITE_SIZE_BITS
        && bullet.sprite_height_bits == STRAIGHT_SPRITE_SIZE_BITS
        && validate_timer(bullet.age, true)
        && validate_timer(bullet.sprite_timer, false);
    if !valid {
        return Err(LifecycleError::InvalidBullet { slot: slot as u8 });
    }
    Ok(())
}

fn in_bounds(
    position: Vec3Bits,
    width_bits: u32,
    height_bits: u32,
) -> Result<bool, ArithmeticError> {
    let half_width = pc24::mul(width_bits, HALF_BITS)?;
    let half_height = pc24::mul(height_bits, HALF_BITS)?;
    if pc24::compare(pc24::add(position.x, half_width)?, 0)? == Ordering::Less {
        return Ok(false);
    }
    if pc24::compare(
        pc24::add(position.x, pc24::negate(half_width)?)?,
        ARCADE_WIDTH_BITS,
    )? == Ordering::Greater
    {
        return Ok(false);
    }
    if pc24::compare(pc24::add(position.y, half_height)?, 0)? == Ordering::Less {
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

fn tick_timer(slot: usize, timer: &mut FullSpeedTimer) -> Result<(), LifecycleError> {
    timer.previous = timer.current;
    timer.current = timer
        .current
        .checked_add(1)
        .ok_or(LifecycleError::TimerOverflow { slot: slot as u8 })?;
    Ok(())
}

fn update_bullets(pool: &mut BulletPool) -> Result<(), LifecycleError> {
    for slot in 0..PLAYER_BULLET_SLOTS {
        let Some(mut bullet) = pool.slots[slot] else {
            continue;
        };
        validate_bullet(slot, bullet, pool.carry[slot])?;
        bullet.position.x = pc24::add(
            bullet.position.x,
            pc24::mul(bullet.velocity.x, FULL_SPEED_BITS)?,
        )?;
        bullet.position.y = pc24::add(
            bullet.position.y,
            pc24::mul(bullet.velocity.y, FULL_SPEED_BITS)?,
        )?;
        bullet.sprite_position = bullet.position;
        let remains_active = in_bounds(
            bullet.position,
            bullet.sprite_width_bits,
            bullet.sprite_height_bits,
        )?;

        // Script 0x440 is fixed to the observed nonterminating straight-bullet
        // ANM profile. ExecuteScript and the bullet age timer both tick even
        // when the preceding bounds check has just reclaimed the slot.
        tick_timer(slot, &mut bullet.sprite_timer)?;
        tick_timer(slot, &mut bullet.age)?;
        pool.slots[slot] = remains_active.then_some(bullet);
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

fn spawn_bullets(
    pool: &mut BulletPool,
    state: ShootingPlayerState,
    timer: u8,
) -> Result<(), LifecycleError> {
    let slot_states = core::array::from_fn(|slot| {
        if pool.slots[slot].is_some() {
            BULLET_STATE_FIRED
        } else {
            0
        }
    });
    let output = spawn_reimu_a(SpawnInput {
        timer,
        current_power: FIXED_POWER,
        player_position: Vec3Bits {
            x: state.enclosing.position.x_bits,
            y: state.enclosing.position.y_bits,
            z: PLAYER_POSITION_Z_BITS,
        },
        // Rank 1 never selects an orb source, so these are deliberately not
        // admitted as unconstrained per-frame witness values.
        orb_positions: [Vec3Bits::default(); 2],
        slot_states,
        slot_carry: pool.carry,
    })?;
    for allocation in output
        .allocations
        .iter()
        .copied()
        .take(usize::from(output.allocation_count))
    {
        let slot = usize::from(allocation.slot);
        if pool.slots[slot].is_some() {
            return Err(LifecycleError::InvalidBullet {
                slot: allocation.slot,
            });
        }
        let bullet = initialized_bullet(allocation);
        validate_bullet(slot, bullet, pool.carry[slot])?;
        pool.slots[slot] = Some(bullet);
    }
    Ok(())
}

/// Advances one frame using only the prior closed state and replay input mask.
pub fn step_player_bullet_lifecycle(
    config: PlayerConfig,
    state: PlayerBulletLifecycleState,
    input: u16,
) -> Result<PlayerBulletLifecycleState, LifecycleError> {
    if config != reimu_a() {
        return Err(LifecycleError::WrongRoute(config));
    }
    if state.shooting.enclosing.game_frame >= PROFILE_LAST_GAME_FRAME {
        return Err(LifecycleError::ProfileEnded(
            state.shooting.enclosing.game_frame,
        ));
    }
    let (shooting, effects) = step_shooting_player(config, state.shooting, input)?;
    let mut bullets = state.bullets;
    update_bullets(&mut bullets)?;
    if let Some(timer) = effects.spawn_bullets_timer {
        spawn_bullets(&mut bullets, shooting, timer)?;
    }
    Ok(PlayerBulletLifecycleState { shooting, bullets })
}

#[cfg(test)]
mod tests {
    use super::*;
    use zkth06_player_shooting::INPUT_SHOOT;

    #[test]
    fn anchor_and_profile_boundary_are_not_witness_supplied() {
        let state = retail_lifecycle_anchor_state(reimu_a()).unwrap();
        assert!(state.bullets.slots.iter().all(Option::is_none));
        assert!(state
            .bullets
            .carry
            .iter()
            .all(|value| *value == SlotCarry::default()));
        let mut end = state;
        end.shooting.enclosing.game_frame = PROFILE_LAST_GAME_FRAME;
        assert_eq!(
            step_player_bullet_lifecycle(reimu_a(), end, 0),
            Err(LifecycleError::ProfileEnded(PROFILE_LAST_GAME_FRAME))
        );
    }

    #[test]
    fn straight_bullet_moves_and_reclaims_without_external_slot_state() {
        let mut state = retail_lifecycle_anchor_state(reimu_a()).unwrap();
        for frame in 2..=34 {
            state = step_player_bullet_lifecycle(reimu_a(), state, 0).unwrap();
            assert_eq!(state.shooting.enclosing.game_frame, frame);
        }
        state = step_player_bullet_lifecycle(reimu_a(), state, INPUT_SHOOT).unwrap();
        let first = state.bullets.slots[0].unwrap();
        assert_eq!(state.shooting.enclosing.game_frame, 35);
        assert_eq!(first.position.y, 384.0_f32.to_bits());
        assert_eq!(
            first.sprite_timer,
            FullSpeedTimer {
                previous: 0,
                current: 1
            }
        );
        for _ in 36..=67 {
            state = step_player_bullet_lifecycle(reimu_a(), state, 0).unwrap();
        }
        assert_eq!(state.bullets.slots[0].unwrap().position.y, 0);
        state = step_player_bullet_lifecycle(reimu_a(), state, 0).unwrap();
        assert!(state.bullets.slots[0].is_none());
    }

    #[test]
    fn malformed_active_state_fails_closed() {
        let mut state = retail_lifecycle_anchor_state(reimu_a()).unwrap();
        state = step_player_bullet_lifecycle(reimu_a(), state, INPUT_SHOOT).unwrap();
        state.bullets.slots[0].as_mut().unwrap().sprite_width_bits = 0;
        assert_eq!(
            step_player_bullet_lifecycle(reimu_a(), state, 0),
            Err(LifecycleError::InvalidBullet { slot: 0 })
        );
    }
}

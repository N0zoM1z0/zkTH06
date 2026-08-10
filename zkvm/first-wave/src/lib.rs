#![no_std]
#![forbid(unsafe_code)]

//! Closed continuation through the complete first Stage-1 Enemy wave.
//!
//! The anchor is the frame-208 state derived by `zkth06-early-gameplay`.
//! Thereafter this transition owns the complete 80-slot Player-bullet state,
//! including every collided bullet, and derives the remaining four deaths at
//! frames 213, 219, 224, and 229.  The profile ends before a death-spawned item
//! first writes score at frame 249.  RNG, effects, items, and the omitted Sub0
//! shooting side effects are therefore finite-prefix noninterference
//! obligations rather than witness inputs.

use core::cmp::Ordering;

use zkth06_early_gameplay::{EarlyEnemy, EarlyGameplayState, EARLY_ENEMY_SLOTS};
use zkth06_player_bullet_lifecycle::{
    ActiveBullet, BulletPool, FullSpeedTimer, LifecycleError, PlayerBulletLifecycleState, Vec2Bits,
    Vec3Bits, ACTIVE_SPRITE_FLAGS, ARCADE_HEIGHT_BITS, ARCADE_WIDTH_BITS, FIXED_POWER,
    FULL_SPEED_BITS, HALF_BITS, PLAYER_POSITION_Z_BITS, STRAIGHT_DAMAGE, STRAIGHT_DIRECTION_BITS,
    STRAIGHT_SIZE_BITS, STRAIGHT_SPEED_BITS, STRAIGHT_SPRITE_SIZE_BITS, STRAIGHT_VELOCITY_X_BITS,
    STRAIGHT_VELOCITY_Y_BITS,
};
use zkth06_player_bullets::{
    spawn_reimu_a, InitializedBullet, SpawnError, SpawnInput, BULLET_STATE_COLLIDED,
    BULLET_STATE_FIRED, BULLET_STATE_UNUSED, BULLET_Z_BITS, ONE_BITS, PLAYER_BULLET_ANM,
    PLAYER_BULLET_SLOTS,
};
use zkth06_player_motion::pc24::{self, ArithmeticError};
use zkth06_player_shooting::{step_shooting_player, ShootingError};

pub const ANCHOR_GAME_FRAME: u32 = 208;
pub const PROFILE_LAST_GAME_FRAME: u32 = 229;
pub const FIRST_WAVE_DEATH_FRAMES: [u32; EARLY_ENEMY_SLOTS] = [208, 213, 219, 224, 229];

const ZERO_BITS: u32 = 0;
const NEGATIVE_999_BITS: u32 = 0xc479_c000;
const ENEMY_HALF_HITBOX_BITS: u32 = 0x4160_0000;
const BULLET_HALF_SIZE_BITS: u32 = 0x40c0_0000;
const ONE_EIGHTH_BITS: u32 = 0x3e00_0000;
const SUB0_INITIAL_AXIS_X_BITS: u32 = 0xb3bb_bd2e;
const SUB0_ANGULAR_VELOCITY_BITS: u32 = 0xbcc9_0fdb;
const TWO_BITS: u32 = 0x4000_0000;
const COLLIDED_POSITION_Z_BITS: u32 = 0x3dcc_cccd;
const COLLIDED_SPRITE_FLAGS: u32 = 0x0000_1007;
const COLLIDED_ACTIVE_SPRITE: u16 = 1090;
const COLLIDED_ANM_FILE: u16 = 1120;
const COLLIDED_SPRITE_SIZE_BITS: u32 = 0x4180_0000;

// Fixed x87 `sincosmul(angle, 2.0f)` outputs for the only curved Sub0
// ECL times reachable after the frame-208 anchor.  Index zero is time 41.
const CURVED_AXIS_BY_ECL_TIME: [Vec2Bits; 29] = [
    Vec2Bits {
        x: 0x3d49_0a7e,
        y: 0x3fff_ec43,
    }, // 41
    Vec2Bits {
        x: 0x3dc8_fb09,
        y: 0x3fff_b10f,
    },
    Vec2Bits {
        x: 0x3e16_a8eb,
        y: 0x3fff_4e6e,
    },
    Vec2Bits {
        x: 0x3e48_bd16,
        y: 0x3ffe_c46e,
    },
    Vec2Bits {
        x: 0x3e7a_b24c,
        y: 0x3ffe_1324,
    },
    Vec2Bits {
        x: 0x3e96_406d,
        y: 0x3ffd_3aad,
    },
    Vec2Bits {
        x: 0x3eaf_1088,
        y: 0x3ffc_3b29,
    },
    Vec2Bits {
        x: 0x3ec7_c5a5,
        y: 0x3ffb_14c0,
    },
    Vec2Bits {
        x: 0x3ee0_5bf3,
        y: 0x3ff9_c79f,
    },
    Vec2Bits {
        x: 0x3ef8_cfa9,
        y: 0x3ff8_53fa,
    }, // 50
    Vec2Bits {
        x: 0x3f08_8e80,
        y: 0x3ff6_ba0a,
    },
    Vec2Bits {
        x: 0x3f14_a01d,
        y: 0x3ff4_fa0e,
    },
    Vec2Bits {
        x: 0x3f20_9acf,
        y: 0x3ff3_144b,
    },
    Vec2Bits {
        x: 0x3f2c_7cbc,
        y: 0x3ff1_090c,
    },
    Vec2Bits {
        x: 0x3f38_4411,
        y: 0x3fee_d8a2,
    },
    Vec2Bits {
        x: 0x3f43_eefb,
        y: 0x3fec_8364,
    },
    Vec2Bits {
        x: 0x3f4f_7baf,
        y: 0x3fea_09ad,
    },
    Vec2Bits {
        x: 0x3f5a_e864,
        y: 0x3fe7_6bde,
    },
    Vec2Bits {
        x: 0x3f66_3357,
        y: 0x3fe4_aa60,
    },
    Vec2Bits {
        x: 0x3f71_5acb,
        y: 0x3fe1_c5a0,
    }, // 60
    Vec2Bits {
        x: 0x3f7c_5d07,
        y: 0x3fde_be0e,
    },
    Vec2Bits {
        x: 0x3f83_9c2c,
        y: 0x3fdb_9424,
    },
    Vec2Bits {
        x: 0x3f88_f58a,
        y: 0x3fd8_485d,
    },
    Vec2Bits {
        x: 0x3f8e_39c9,
        y: 0x3fd4_db3c,
    },
    Vec2Bits {
        x: 0x3f93_681a,
        y: 0x3fd1_4d48,
    },
    Vec2Bits {
        x: 0x3f98_7fb0,
        y: 0x3fcd_9f0e,
    },
    Vec2Bits {
        x: 0x3f9d_7fc2,
        y: 0x3fc9_d11e,
    },
    Vec2Bits {
        x: 0x3fa2_678a,
        y: 0x3fc5_e40f,
    },
    Vec2Bits {
        x: 0x3fa7_3648,
        y: 0x3fc1_d87d,
    }, // 69
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FirstWaveState {
    pub player: PlayerBulletLifecycleState,
    pub bullet_states: [u8; PLAYER_BULLET_SLOTS],
    pub enemies: [Option<EarlyEnemy>; EARLY_ENEMY_SLOTS],
    pub score: u32,
    pub last_enemy_hit: Vec3Bits,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FirstWaveError {
    WrongAnchor(u32),
    ProfileEnded(u32),
    InvalidBullet { slot: u8 },
    InvalidEnemy { slot: u8 },
    MissingEnemy { slot: u8 },
    UnexpectedEnemy { slot: u8 },
    UnsupportedEclTime(i32),
    TimerOverflow { slot: u8 },
    ScoreOverflow,
    LifeOverflow,
    Lifecycle(LifecycleError),
    Shooting(ShootingError),
    Spawn(SpawnError),
    Arithmetic(ArithmeticError),
}

impl From<LifecycleError> for FirstWaveError {
    fn from(value: LifecycleError) -> Self {
        Self::Lifecycle(value)
    }
}

impl From<ShootingError> for FirstWaveError {
    fn from(value: ShootingError) -> Self {
        Self::Shooting(value)
    }
}

impl From<SpawnError> for FirstWaveError {
    fn from(value: SpawnError) -> Self {
        Self::Spawn(value)
    }
}

impl From<ArithmeticError> for FirstWaveError {
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

fn axis_for_time(time: i32) -> Result<Vec2Bits, FirstWaveError> {
    if (2..=40).contains(&time) {
        return Ok(Vec2Bits {
            x: SUB0_INITIAL_AXIS_X_BITS,
            y: TWO_BITS,
        });
    }
    let index = usize::try_from(time - 41).map_err(|_| FirstWaveError::UnsupportedEclTime(time))?;
    CURVED_AXIS_BY_ECL_TIME
        .get(index)
        .copied()
        .ok_or(FirstWaveError::UnsupportedEclTime(time))
}

fn expected_enemy(frame: u32, slot: usize) -> bool {
    frame < FIRST_WAVE_DEATH_FRAMES[slot]
}

fn validate_enemy(slot: usize, enemy: EarlyEnemy) -> Result<(), FirstWaveError> {
    if enemy.position.z != ZERO_BITS
        || enemy.axis_speed != axis_for_time(enemy.ecl_time)?
        || enemy.angular_velocity_bits
            != if enemy.ecl_time <= 40 {
                ZERO_BITS
            } else {
                SUB0_ANGULAR_VELOCITY_BITS
            }
        || enemy.ecl_time < 2
        || enemy.life <= 0
        || !enemy.has_been_in_bounds
    {
        return Err(FirstWaveError::InvalidEnemy { slot: slot as u8 });
    }
    Ok(())
}

fn validate_timer(timer: FullSpeedTimer, allow_popup: bool) -> bool {
    (allow_popup && timer.previous == -999 && timer.current == 0)
        || (timer.current > 0 && timer.previous == timer.current - 1)
}

fn validate_bullet(
    frame: u32,
    slot: usize,
    state: u8,
    bullet: ActiveBullet,
    pool: &BulletPool,
) -> Result<(), FirstWaveError> {
    let carry = pool.carry[slot];
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
        && validate_timer(bullet.age, true)
        && validate_timer(bullet.sprite_timer, false);
    let state_valid = match state {
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
            let newly_collided_sprite = bullet.sprite_timer.current == 1
                && bullet.sprite_position.x == bullet.position.x
                && bullet.sprite_position.y == bullet.position.y
                && bullet.sprite_position.z == BULLET_Z_BITS;
            bullet.position.z == COLLIDED_POSITION_Z_BITS
                && bullet.velocity == Vec2Bits { x: 0xb38c_cde2, y: 0xbfc0_0000 }
                && (bullet.sprite_position == bullet.position || newly_collided_sprite)
                && bullet.sprite_flags == COLLIDED_SPRITE_FLAGS
                && bullet.sprite_active_index == COLLIDED_ACTIVE_SPRITE
                && bullet.sprite_anm_file_index == COLLIDED_ANM_FILE
                && bullet.sprite_width_bits == COLLIDED_SPRITE_SIZE_BITS
                && bullet.sprite_height_bits == COLLIDED_SPRITE_SIZE_BITS
                // The earliest collision ANM exits at frame 238.  This profile
                // ends at 229, so every reachable collision script only ticks.
                && bullet.sprite_timer.current <= 22
                && frame <= PROFILE_LAST_GAME_FRAME
        }
        _ => false,
    };
    if !common || !state_valid {
        return Err(FirstWaveError::InvalidBullet { slot: slot as u8 });
    }
    Ok(())
}

fn validate_pre_state(state: &FirstWaveState) -> Result<(), FirstWaveError> {
    let frame = state.player.shooting.enclosing.game_frame;
    if !(ANCHOR_GAME_FRAME..=PROFILE_LAST_GAME_FRAME).contains(&frame) {
        return Err(FirstWaveError::WrongAnchor(frame));
    }
    for slot in 0..PLAYER_BULLET_SLOTS {
        match (state.bullet_states[slot], state.player.bullets.slots[slot]) {
            (BULLET_STATE_UNUSED, None) => {}
            (BULLET_STATE_FIRED | BULLET_STATE_COLLIDED, Some(bullet)) => {
                validate_bullet(
                    frame,
                    slot,
                    state.bullet_states[slot],
                    bullet,
                    &state.player.bullets,
                )?;
            }
            _ => return Err(FirstWaveError::InvalidBullet { slot: slot as u8 }),
        }
    }
    for slot in 0..EARLY_ENEMY_SLOTS {
        match (expected_enemy(frame, slot), state.enemies[slot]) {
            (true, Some(enemy)) => validate_enemy(slot, enemy)?,
            (true, None) => return Err(FirstWaveError::MissingEnemy { slot: slot as u8 }),
            (false, Some(_)) => return Err(FirstWaveError::UnexpectedEnemy { slot: slot as u8 }),
            (false, None) => {}
        }
    }
    Ok(())
}

/// Converts the derived frame-208 enclosing state into the richer multi-
/// collision state.  No bullet or Enemy witness is introduced.
pub fn from_first_collision(state: EarlyGameplayState) -> Result<FirstWaveState, FirstWaveError> {
    let frame = state.player.shooting.enclosing.game_frame;
    if frame != ANCHOR_GAME_FRAME || state.collided_slot != Some(2) {
        return Err(FirstWaveError::WrongAnchor(frame));
    }
    let bullet_states = core::array::from_fn(|slot| {
        if state.player.bullets.slots[slot].is_none() {
            BULLET_STATE_UNUSED
        } else if state.collided_slot == Some(slot as u8) {
            BULLET_STATE_COLLIDED
        } else {
            BULLET_STATE_FIRED
        }
    });
    let result = FirstWaveState {
        player: state.player,
        bullet_states,
        enemies: state.enemies,
        score: state.score,
        last_enemy_hit: state.last_enemy_hit,
    };
    validate_pre_state(&result)?;
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

fn tick_timer(slot: usize, timer: &mut FullSpeedTimer) -> Result<(), FirstWaveError> {
    timer.previous = timer.current;
    timer.current = timer
        .current
        .checked_add(1)
        .ok_or(FirstWaveError::TimerOverflow { slot: slot as u8 })?;
    Ok(())
}

fn update_bullets(state: &mut FirstWaveState) -> Result<(), FirstWaveError> {
    let frame = state.player.shooting.enclosing.game_frame;
    for slot in 0..PLAYER_BULLET_SLOTS {
        let bullet_state = state.bullet_states[slot];
        let Some(mut bullet) = state.player.bullets.slots[slot] else {
            continue;
        };
        validate_bullet(frame - 1, slot, bullet_state, bullet, &state.player.bullets)?;
        bullet.position.x = pc24::add(
            bullet.position.x,
            pc24::mul(bullet.velocity.x, FULL_SPEED_BITS)?,
        )?;
        bullet.position.y = pc24::add(
            bullet.position.y,
            pc24::mul(bullet.velocity.y, FULL_SPEED_BITS)?,
        )?;
        bullet.sprite_position = bullet.position;
        let remains = in_bounds(
            bullet.position,
            bullet.sprite_width_bits,
            bullet.sprite_height_bits,
        )?;
        tick_timer(slot, &mut bullet.sprite_timer)?;
        tick_timer(slot, &mut bullet.age)?;
        if remains {
            state.player.bullets.slots[slot] = Some(bullet);
        } else {
            state.player.bullets.slots[slot] = None;
            state.bullet_states[slot] = BULLET_STATE_UNUSED;
        }
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

fn spawn_bullets(state: &mut FirstWaveState, timer: u8) -> Result<(), FirstWaveError> {
    let output = spawn_reimu_a(SpawnInput {
        timer,
        current_power: FIXED_POWER,
        player_position: Vec3Bits {
            x: state.player.shooting.enclosing.position.x_bits,
            y: state.player.shooting.enclosing.position.y_bits,
            z: PLAYER_POSITION_Z_BITS,
        },
        orb_positions: [Vec3Bits::default(); 2],
        slot_states: state.bullet_states,
        slot_carry: state.player.bullets.carry,
    })?;
    for allocation in output
        .allocations
        .iter()
        .copied()
        .take(usize::from(output.allocation_count))
    {
        let slot = usize::from(allocation.slot);
        if state.player.bullets.slots[slot].is_some()
            || state.bullet_states[slot] != BULLET_STATE_UNUSED
        {
            return Err(FirstWaveError::InvalidBullet {
                slot: allocation.slot,
            });
        }
        state.player.bullets.slots[slot] = Some(initialized_bullet(allocation));
        state.bullet_states[slot] = BULLET_STATE_FIRED;
    }
    Ok(())
}

fn step_player_phase(
    mut state: FirstWaveState,
    input: u16,
) -> Result<FirstWaveState, FirstWaveError> {
    let (shooting, effects) = step_shooting_player(
        zkth06_player_bullet_lifecycle::reimu_a(),
        state.player.shooting,
        input,
    )?;
    state.player.shooting = shooting;
    update_bullets(&mut state)?;
    if let Some(timer) = effects.spawn_bullets_timer {
        spawn_bullets(&mut state, timer)?;
    }
    Ok(state)
}

fn move_enemy(enemy: &mut EarlyEnemy) -> Result<(), FirstWaveError> {
    enemy.position.x = pc24::add(enemy.position.x, enemy.axis_speed.x)?;
    enemy.position.y = pc24::add(enemy.position.y, enemy.axis_speed.y)?;
    Ok(())
}

fn advance_surviving_ecl(enemy: &mut EarlyEnemy) -> Result<(), FirstWaveError> {
    let next = enemy
        .ecl_time
        .checked_add(1)
        .ok_or(FirstWaveError::UnsupportedEclTime(enemy.ecl_time))?;
    if enemy.ecl_time == 40 {
        enemy.angular_velocity_bits = SUB0_ANGULAR_VELOCITY_BITS;
    }
    enemy.angle_bits = pc24::add(enemy.angle_bits, enemy.angular_velocity_bits)?;
    enemy.axis_speed = axis_for_time(next)?;
    enemy.ecl_time = next;
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
    Ok(
        pc24::compare(bullet_top, enemy_bottom)? != Ordering::Greater
            && pc24::compare(bullet_left, enemy_right)? != Ordering::Greater
            && pc24::compare(bullet_bottom, enemy_top)? != Ordering::Less
            && pc24::compare(bullet_right, enemy_left)? != Ordering::Less,
    )
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
    bullet.sprite_timer = FullSpeedTimer {
        previous: 0,
        current: 1,
    };
    Ok(())
}

fn calc_damage(state: &mut FirstWaveState, enemy: Vec3Bits) -> Result<i32, FirstWaveError> {
    let mut damage = 0_i32;
    for slot in 0..PLAYER_BULLET_SLOTS {
        if state.bullet_states[slot] != BULLET_STATE_FIRED {
            continue;
        }
        let Some(mut bullet) = state.player.bullets.slots[slot] else {
            return Err(FirstWaveError::InvalidBullet { slot: slot as u8 });
        };
        if !overlaps(bullet, enemy)? {
            continue;
        }
        damage = damage
            .checked_add(i32::from(bullet.damage))
            .ok_or(FirstWaveError::LifeOverflow)?;
        collide_bullet(&mut bullet)?;
        state.player.bullets.slots[slot] = Some(bullet);
        state.bullet_states[slot] = BULLET_STATE_COLLIDED;
    }
    Ok(damage)
}

/// Advances one frame from the derived first-collision anchor through the
/// complete five-Enemy first wave.
pub fn step_first_wave(
    mut state: FirstWaveState,
    input: u16,
) -> Result<FirstWaveState, FirstWaveError> {
    let prior_frame = state.player.shooting.enclosing.game_frame;
    if prior_frame >= PROFILE_LAST_GAME_FRAME {
        return Err(FirstWaveError::ProfileEnded(prior_frame));
    }
    validate_pre_state(&state)?;
    state = step_player_phase(state, input)?;
    state.last_enemy_hit = reset_target();
    for slot in 0..EARLY_ENEMY_SLOTS {
        let Some(mut enemy) = state.enemies[slot] else {
            continue;
        };
        move_enemy(&mut enemy)?;
        let damage = calc_damage(&mut state, enemy.position)?.min(70);
        let damage_score =
            u32::try_from((damage / 5) * 10).map_err(|_| FirstWaveError::ScoreOverflow)?;
        state.score = state
            .score
            .checked_add(damage_score)
            .ok_or(FirstWaveError::ScoreOverflow)?;
        enemy.life = enemy
            .life
            .checked_sub(damage)
            .ok_or(FirstWaveError::LifeOverflow)?;
        if pc24::compare(state.last_enemy_hit.y, enemy.position.y)? == Ordering::Less {
            state.last_enemy_hit = enemy.position;
        }
        if enemy.life <= 0 {
            state.score = state
                .score
                .checked_add(300)
                .ok_or(FirstWaveError::ScoreOverflow)?;
            state.enemies[slot] = None;
            continue;
        }
        advance_surviving_ecl(&mut enemy)?;
        state.enemies[slot] = Some(enemy);
    }
    validate_pre_state(&state)?;
    Ok(state)
}

pub fn collision_count(state: &FirstWaveState) -> u32 {
    state
        .bullet_states
        .iter()
        .filter(|&&value| value == BULLET_STATE_COLLIDED)
        .count() as u32
}

#[cfg(test)]
mod tests {
    use super::*;
    use zkth06_early_gameplay::retail_early_gameplay_anchor;

    #[test]
    fn conversion_rejects_a_state_before_the_derived_boundary() {
        let early = retail_early_gameplay_anchor().unwrap();
        assert_eq!(
            from_first_collision(early),
            Err(FirstWaveError::WrongAnchor(1))
        );
    }
}

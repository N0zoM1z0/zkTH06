#![no_std]
#![forbid(unsafe_code)]

//! Enclosing fixed-route gameplay transition through the first Enemy hit.
//!
//! This composes the linked Reimu-A Player/bullet state with the first five
//! Stage-1 `Sub0` enemies. Timeline spawns, movement, in-bounds gating, ECL
//! time, AABB damage, bullet collision state, enemy life, targeting, death,
//! and score are derived from the prior state and replay input. The curved
//! `sincosmul` outputs are a fixed lookup indexed by derived ECL time; they are
//! executable constants bound to the finite retail/reference audit, not
//! witness values. Proving that lookup against pinned x87 trigonometry remains
//! an explicit arithmetic-refinement obligation.

use core::cmp::Ordering;

use zkth06_player_bullet_lifecycle::{
    reimu_a, retail_lifecycle_anchor_state, step_player_bullet_lifecycle,
    step_player_phase_at_first_collision, ActiveBullet, LifecycleError, PlayerBulletLifecycleState,
    Vec2Bits, Vec3Bits, PROFILE_LAST_GAME_FRAME as PLAYER_LIFECYCLE_LAST_GAME_FRAME,
};
use zkth06_player_bullets::PLAYER_BULLET_SLOTS;
use zkth06_player_motion::pc24::{self, ArithmeticError};

pub const PROFILE_LAST_GAME_FRAME: u32 = 208;
pub const FIRST_ENEMY_SPAWN_GAME_FRAME: u32 = 129;
pub const FIRST_DAMAGE_CALL_GAME_FRAME: u32 = 137;
pub const FIRST_COLLISION_GAME_FRAME: u32 = 208;
pub const EARLY_ENEMY_SLOTS: usize = 5;

const ZERO_BITS: u32 = 0;
const NEGATIVE_999_BITS: u32 = 0xc479_c000;
const ONE_EIGHTH_BITS: u32 = 0x3e00_0000;
const ENEMY_HITBOX_XY_BITS: u32 = 0x41e0_0000;
const ENEMY_HITBOX_Z_BITS: u32 = 0x4200_0000;
const ENEMY_HALF_HITBOX_BITS: u32 = 0x4160_0000;
const BULLET_HALF_SIZE_BITS: u32 = 0x40c0_0000;
const PI_OVER_TWO_BITS: u32 = 0x3fc9_0fdb;
const SUB0_ANGULAR_VELOCITY_BITS: u32 = 0xbcc9_0fdb;
const SUB0_INITIAL_AXIS_X_BITS: u32 = 0xb3bb_bd2e;
const TWO_BITS: u32 = 0x4000_0000;
const COLLIDED_POSITION_Z_BITS: u32 = 0x3dcc_cccd;
const COLLIDED_SPRITE_FLAGS: u32 = 0x0000_1007;
const COLLIDED_ACTIVE_SPRITE: u16 = 1090;
const COLLIDED_ANM_FILE: u16 = 1120;
const COLLIDED_SPRITE_SIZE_BITS: u32 = 0x4180_0000;

const SPAWN_FRAMES: [u32; EARLY_ENEMY_SLOTS] = [129, 145, 161, 177, 193];
const SPAWN_X_BITS: [u32; EARLY_ENEMY_SLOTS] = [
    0x4270_0000,
    0x4288_0000,
    0x4298_0000,
    0x42a8_0000,
    0x42b8_0000,
];
const SPAWN_LIFE: [i32; EARLY_ENEMY_SLOTS] = [8, 32, 32, 32, 32];

// x87 `sincosmul(angle, 2.0f)` outputs after Sub0's time-40 turn.
// Index zero is ECL time 41. All entries were matched bit-for-bit between the
// pinned retail executable and the independently built reference runner.
const CURVED_AXIS_BY_ECL_TIME: [Vec2Bits; 40] = [
    Vec2Bits {
        x: 0x3d49_0a7e,
        y: 0x3fff_ec43,
    }, // 41
    Vec2Bits {
        x: 0x3dc8_fb09,
        y: 0x3fff_b10f,
    }, // 42
    Vec2Bits {
        x: 0x3e16_a8eb,
        y: 0x3fff_4e6e,
    }, // 43
    Vec2Bits {
        x: 0x3e48_bd16,
        y: 0x3ffe_c46e,
    }, // 44
    Vec2Bits {
        x: 0x3e7a_b24c,
        y: 0x3ffe_1324,
    }, // 45
    Vec2Bits {
        x: 0x3e96_406d,
        y: 0x3ffd_3aad,
    }, // 46
    Vec2Bits {
        x: 0x3eaf_1088,
        y: 0x3ffc_3b29,
    }, // 47
    Vec2Bits {
        x: 0x3ec7_c5a5,
        y: 0x3ffb_14c0,
    }, // 48
    Vec2Bits {
        x: 0x3ee0_5bf3,
        y: 0x3ff9_c79f,
    }, // 49
    Vec2Bits {
        x: 0x3ef8_cfa9,
        y: 0x3ff8_53fa,
    }, // 50
    Vec2Bits {
        x: 0x3f08_8e80,
        y: 0x3ff6_ba0a,
    }, // 51
    Vec2Bits {
        x: 0x3f14_a01d,
        y: 0x3ff4_fa0e,
    }, // 52
    Vec2Bits {
        x: 0x3f20_9acf,
        y: 0x3ff3_144b,
    }, // 53
    Vec2Bits {
        x: 0x3f2c_7cbc,
        y: 0x3ff1_090c,
    }, // 54
    Vec2Bits {
        x: 0x3f38_4411,
        y: 0x3fee_d8a2,
    }, // 55
    Vec2Bits {
        x: 0x3f43_eefb,
        y: 0x3fec_8364,
    }, // 56
    Vec2Bits {
        x: 0x3f4f_7baf,
        y: 0x3fea_09ad,
    }, // 57
    Vec2Bits {
        x: 0x3f5a_e864,
        y: 0x3fe7_6bde,
    }, // 58
    Vec2Bits {
        x: 0x3f66_3357,
        y: 0x3fe4_aa60,
    }, // 59
    Vec2Bits {
        x: 0x3f71_5acb,
        y: 0x3fe1_c5a0,
    }, // 60
    Vec2Bits {
        x: 0x3f7c_5d07,
        y: 0x3fde_be0e,
    }, // 61
    Vec2Bits {
        x: 0x3f83_9c2c,
        y: 0x3fdb_9424,
    }, // 62
    Vec2Bits {
        x: 0x3f88_f58a,
        y: 0x3fd8_485d,
    }, // 63
    Vec2Bits {
        x: 0x3f8e_39c9,
        y: 0x3fd4_db3c,
    }, // 64
    Vec2Bits {
        x: 0x3f93_681a,
        y: 0x3fd1_4d48,
    }, // 65
    Vec2Bits {
        x: 0x3f98_7fb0,
        y: 0x3fcd_9f0e,
    }, // 66
    Vec2Bits {
        x: 0x3f9d_7fc2,
        y: 0x3fc9_d11e,
    }, // 67
    Vec2Bits {
        x: 0x3fa2_678a,
        y: 0x3fc5_e40f,
    }, // 68
    Vec2Bits {
        x: 0x3fa7_3648,
        y: 0x3fc1_d87d,
    }, // 69
    Vec2Bits {
        x: 0x3fab_eb3c,
        y: 0x3fbd_af06,
    }, // 70
    Vec2Bits {
        x: 0x3fb0_85ad,
        y: 0x3fb9_684f,
    }, // 71
    Vec2Bits {
        x: 0x3fb5_04e6,
        y: 0x3fb5_0500,
    }, // 72
    Vec2Bits {
        x: 0x3fb9_6835,
        y: 0x3fb0_85c8,
    }, // 73
    Vec2Bits {
        x: 0x3fbd_aeed,
        y: 0x3fab_eb57,
    }, // 74
    Vec2Bits {
        x: 0x3fc1_d865,
        y: 0x3fa7_3663,
    }, // 75
    Vec2Bits {
        x: 0x3fc5_e3f8,
        y: 0x3fa2_67a7,
    }, // 76
    Vec2Bits {
        x: 0x3fc9_d108,
        y: 0x3f9d_7fdf,
    }, // 77
    Vec2Bits {
        x: 0x3fcd_9ef8,
        y: 0x3f98_7fce,
    }, // 78
    Vec2Bits {
        x: 0x3fd1_4d33,
        y: 0x3f93_6838,
    }, // 79
    Vec2Bits {
        x: 0x3fd4_db28,
        y: 0x3f8e_39e8,
    }, // 80
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EarlyEnemy {
    pub position: Vec3Bits,
    pub axis_speed: Vec2Bits,
    pub angle_bits: u32,
    pub angular_velocity_bits: u32,
    pub ecl_time: i32,
    pub life: i32,
    pub has_been_in_bounds: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EarlyGameplayState {
    pub player: PlayerBulletLifecycleState,
    pub enemies: [Option<EarlyEnemy>; EARLY_ENEMY_SLOTS],
    pub score: u32,
    pub last_enemy_hit: Vec3Bits,
    pub collided_slot: Option<u8>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EarlyGameplayError {
    ProfileEnded(u32),
    Lifecycle(LifecycleError),
    Arithmetic(ArithmeticError),
    InvalidEnemy { slot: u8 },
    MissingEnemy { slot: u8 },
    UnexpectedEnemy { slot: u8 },
    UnsupportedEclTime(i32),
    MultipleCollisions,
    ScoreOverflow,
    LifeOverflow,
}

impl From<LifecycleError> for EarlyGameplayError {
    fn from(value: LifecycleError) -> Self {
        Self::Lifecycle(value)
    }
}

impl From<ArithmeticError> for EarlyGameplayError {
    fn from(value: ArithmeticError) -> Self {
        Self::Arithmetic(value)
    }
}

pub fn retail_early_gameplay_anchor() -> Result<EarlyGameplayState, EarlyGameplayError> {
    Ok(EarlyGameplayState {
        player: retail_lifecycle_anchor_state(reimu_a())?,
        enemies: [None; EARLY_ENEMY_SLOTS],
        score: 0,
        last_enemy_hit: reset_target(),
        collided_slot: None,
    })
}

const fn reset_target() -> Vec3Bits {
    Vec3Bits {
        x: NEGATIVE_999_BITS,
        y: NEGATIVE_999_BITS,
        z: ZERO_BITS,
    }
}

fn axis_for_time(time: i32) -> Result<Vec2Bits, EarlyGameplayError> {
    if (2..=40).contains(&time) {
        return Ok(Vec2Bits {
            x: SUB0_INITIAL_AXIS_X_BITS,
            y: TWO_BITS,
        });
    }
    let index =
        usize::try_from(time - 41).map_err(|_| EarlyGameplayError::UnsupportedEclTime(time))?;
    CURVED_AXIS_BY_ECL_TIME
        .get(index)
        .copied()
        .ok_or(EarlyGameplayError::UnsupportedEclTime(time))
}

fn angle_for_time(time: i32) -> Result<u32, EarlyGameplayError> {
    if !(2..=80).contains(&time) {
        return Err(EarlyGameplayError::UnsupportedEclTime(time));
    }
    let mut angle = PI_OVER_TWO_BITS;
    for _ in 40..time {
        angle = pc24::add(angle, SUB0_ANGULAR_VELOCITY_BITS)?;
    }
    Ok(angle)
}

fn validate_enemy(slot: usize, enemy: EarlyEnemy) -> Result<(), EarlyGameplayError> {
    let expected_angular = if enemy.ecl_time <= 40 {
        ZERO_BITS
    } else {
        SUB0_ANGULAR_VELOCITY_BITS
    };
    if enemy.position.z != ZERO_BITS
        || enemy.axis_speed != axis_for_time(enemy.ecl_time)?
        || enemy.angle_bits != angle_for_time(enemy.ecl_time)?
        || enemy.angular_velocity_bits != expected_angular
        || enemy.life <= 0
        || enemy.ecl_time < 2
    {
        return Err(EarlyGameplayError::InvalidEnemy { slot: slot as u8 });
    }
    Ok(())
}

fn spawn_enemy(slot: usize) -> EarlyEnemy {
    EarlyEnemy {
        position: Vec3Bits {
            x: SPAWN_X_BITS[slot],
            y: (-32.0_f32).to_bits(),
            z: ZERO_BITS,
        },
        axis_speed: Vec2Bits {
            x: SUB0_INITIAL_AXIS_X_BITS,
            y: TWO_BITS,
        },
        angle_bits: PI_OVER_TWO_BITS,
        angular_velocity_bits: ZERO_BITS,
        // SpawnEnemy executes Sub0 once at time 0; the enclosing manager loop
        // will move and tick this time-1 intermediate state in the same frame.
        ecl_time: 1,
        life: SPAWN_LIFE[slot],
        has_been_in_bounds: false,
    }
}

fn move_enemy(enemy: &mut EarlyEnemy) -> Result<(), EarlyGameplayError> {
    enemy.position.x = pc24::add(enemy.position.x, enemy.axis_speed.x)?;
    enemy.position.y = pc24::add(enemy.position.y, enemy.axis_speed.y)?;
    Ok(())
}

fn becomes_in_bounds(position: Vec3Bits) -> Result<bool, ArithmeticError> {
    // Script 769's early Sub0 sprite is 28x28. All selected x values and the
    // lower/right edges remain in bounds, but retaining all four comparisons
    // keeps the partial evaluation visibly aligned with GameManager::IsInBounds.
    let left = pc24::add(position.x, pc24::negate(ENEMY_HALF_HITBOX_BITS)?)?;
    let right = pc24::add(position.x, ENEMY_HALF_HITBOX_BITS)?;
    let top = pc24::add(position.y, ENEMY_HALF_HITBOX_BITS)?;
    let bottom = pc24::add(position.y, pc24::negate(ENEMY_HALF_HITBOX_BITS)?)?;
    Ok(pc24::compare(right, ZERO_BITS)? != Ordering::Less
        && pc24::compare(left, 384.0_f32.to_bits())? != Ordering::Greater
        && pc24::compare(top, ZERO_BITS)? != Ordering::Less
        && pc24::compare(bottom, 448.0_f32.to_bits())? != Ordering::Greater)
}

fn advance_surviving_ecl(enemy: &mut EarlyEnemy) -> Result<(), EarlyGameplayError> {
    let next_time = enemy
        .ecl_time
        .checked_add(1)
        .ok_or(EarlyGameplayError::UnsupportedEclTime(enemy.ecl_time))?;
    if enemy.ecl_time == 40 {
        enemy.angular_velocity_bits = SUB0_ANGULAR_VELOCITY_BITS;
    }
    enemy.angle_bits = pc24::add(enemy.angle_bits, enemy.angular_velocity_bits)?;
    enemy.axis_speed = axis_for_time(next_time)?;
    enemy.ecl_time = next_time;
    Ok(())
}

fn overlaps(bullet: ActiveBullet, enemy_position: Vec3Bits) -> Result<bool, ArithmeticError> {
    let enemy_left = pc24::add(enemy_position.x, pc24::negate(ENEMY_HALF_HITBOX_BITS)?)?;
    let enemy_right = pc24::add(enemy_position.x, ENEMY_HALF_HITBOX_BITS)?;
    let enemy_top = pc24::add(enemy_position.y, pc24::negate(ENEMY_HALF_HITBOX_BITS)?)?;
    let enemy_bottom = pc24::add(enemy_position.y, ENEMY_HALF_HITBOX_BITS)?;
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
    // SetAndExecuteScriptIdx(anmFileIndex + 0x20) enters the fixed rank-1
    // collision script. Its first instruction selects sprite 1090 at 16x16.
    bullet.sprite_flags = COLLIDED_SPRITE_FLAGS;
    bullet.sprite_active_index = COLLIDED_ACTIVE_SPRITE;
    bullet.sprite_anm_file_index = COLLIDED_ANM_FILE;
    bullet.sprite_width_bits = COLLIDED_SPRITE_SIZE_BITS;
    bullet.sprite_height_bits = COLLIDED_SPRITE_SIZE_BITS;
    bullet.sprite_timer.previous = 0;
    bullet.sprite_timer.current = 1;
    Ok(())
}

fn calc_damage(
    state: &mut EarlyGameplayState,
    enemy_position: Vec3Bits,
) -> Result<i32, EarlyGameplayError> {
    let mut damage = 0_i32;
    for slot in 0..PLAYER_BULLET_SLOTS {
        if state.collided_slot == Some(slot as u8) {
            continue;
        }
        let Some(mut bullet) = state.player.bullets.slots[slot] else {
            continue;
        };
        if !overlaps(bullet, enemy_position)? {
            continue;
        }
        damage = damage
            .checked_add(i32::from(bullet.damage))
            .ok_or(EarlyGameplayError::LifeOverflow)?;
        if state.collided_slot.is_some() {
            return Err(EarlyGameplayError::MultipleCollisions);
        }
        collide_bullet(&mut bullet)?;
        state.player.bullets.slots[slot] = Some(bullet);
        state.collided_slot = Some(slot as u8);
    }
    Ok(damage)
}

fn expected_presence(frame: u32, slot: usize) -> bool {
    frame >= SPAWN_FRAMES[slot]
}

fn validate_pre_state(state: &EarlyGameplayState) -> Result<(), EarlyGameplayError> {
    let frame = state.player.shooting.enclosing.game_frame;
    if state.collided_slot.is_some() {
        return Err(EarlyGameplayError::MultipleCollisions);
    }
    for slot in 0..EARLY_ENEMY_SLOTS {
        match (expected_presence(frame, slot), state.enemies[slot]) {
            (true, Some(enemy)) => validate_enemy(slot, enemy)?,
            (true, None) => return Err(EarlyGameplayError::MissingEnemy { slot: slot as u8 }),
            (false, Some(_)) => {
                return Err(EarlyGameplayError::UnexpectedEnemy { slot: slot as u8 })
            }
            (false, None) => {}
        }
    }
    Ok(())
}

/// Advances the linked Player and early-Enemy state by one gameplay frame.
pub fn step_early_gameplay(
    mut state: EarlyGameplayState,
    input: u16,
) -> Result<EarlyGameplayState, EarlyGameplayError> {
    let prior_frame = state.player.shooting.enclosing.game_frame;
    if prior_frame >= PROFILE_LAST_GAME_FRAME {
        return Err(EarlyGameplayError::ProfileEnded(prior_frame));
    }
    validate_pre_state(&state)?;
    state.player = if prior_frame < PLAYER_LIFECYCLE_LAST_GAME_FRAME {
        step_player_bullet_lifecycle(reimu_a(), state.player, input)?
    } else {
        step_player_phase_at_first_collision(reimu_a(), state.player, input)?
    };
    let frame = state.player.shooting.enclosing.game_frame;

    state.last_enemy_hit = reset_target();
    for slot in 0..EARLY_ENEMY_SLOTS {
        if frame == SPAWN_FRAMES[slot] {
            state.enemies[slot] = Some(spawn_enemy(slot));
        }
        let Some(mut enemy) = state.enemies[slot] else {
            continue;
        };
        move_enemy(&mut enemy)?;
        enemy.has_been_in_bounds |= becomes_in_bounds(enemy.position)?;
        if enemy.has_been_in_bounds {
            let damage = calc_damage(&mut state, enemy.position)?.min(70);
            let damage_score =
                u32::try_from((damage / 5) * 10).map_err(|_| EarlyGameplayError::ScoreOverflow)?;
            state.score = state
                .score
                .checked_add(damage_score)
                .ok_or(EarlyGameplayError::ScoreOverflow)?;
            enemy.life = enemy
                .life
                .checked_sub(damage)
                .ok_or(EarlyGameplayError::LifeOverflow)?;
            if pc24::compare(state.last_enemy_hit.y, enemy.position.y)? == Ordering::Less {
                state.last_enemy_hit = enemy.position;
            }
            if enemy.life <= 0 {
                state.score = state
                    .score
                    .checked_add(300)
                    .ok_or(EarlyGameplayError::ScoreOverflow)?;
                state.enemies[slot] = None;
                continue;
            }
        }
        advance_surviving_ecl(&mut enemy)?;
        state.enemies[slot] = Some(enemy);
    }
    Ok(state)
}

/// Executes the unique frame-207 -> frame-208 boundary.
pub fn step_first_collision(
    state: EarlyGameplayState,
    input: u16,
) -> Result<EarlyGameplayState, EarlyGameplayError> {
    let prior_frame = state.player.shooting.enclosing.game_frame;
    if prior_frame != PLAYER_LIFECYCLE_LAST_GAME_FRAME {
        return Err(EarlyGameplayError::ProfileEnded(prior_frame));
    }
    step_early_gameplay(state, input)
}

pub const fn enemy_hitbox() -> Vec3Bits {
    Vec3Bits {
        x: ENEMY_HITBOX_XY_BITS,
        y: ENEMY_HITBOX_XY_BITS,
        z: ENEMY_HITBOX_Z_BITS,
    }
}

pub fn player_bullet_state(state: &EarlyGameplayState, slot: usize) -> u8 {
    if state.player.bullets.slots[slot].is_none() {
        0
    } else if state.collided_slot == Some(slot as u8) {
        2
    } else {
        1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_anchor_has_no_enemy_or_collision_witness() {
        let state = retail_early_gameplay_anchor().unwrap();
        assert_eq!(state.player.shooting.enclosing.game_frame, 1);
        assert!(state.enemies.iter().all(Option::is_none));
        assert_eq!(state.score, 0);
        assert_eq!(state.last_enemy_hit, reset_target());
        assert_eq!(state.collided_slot, None);
    }

    #[test]
    fn fixed_sub0_lookup_is_total_for_reachable_pre_collision_times() {
        for time in 2..=80 {
            axis_for_time(time).unwrap();
            angle_for_time(time).unwrap();
        }
        assert_eq!(
            axis_for_time(81),
            Err(EarlyGameplayError::UnsupportedEclTime(81))
        );
    }
}

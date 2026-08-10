#![no_std]
#![forbid(unsafe_code)]

//! Enclosing Player transition through the shooting-cadence callback boundary.
//!
//! This module extends the closed position/life-timer state with fields written
//! by `Player::HandlePlayerInputs`, `Player::StartFireBulletTimer`, and
//! `Player::UpdateFireBulletsTimer`. It intentionally stops at the
//! `Player::SpawnBullets(player, timer)` call boundary: bullet allocation and
//! character-specific callback geometry are the next refinement layer.
//!
//! The supported profile is full-speed replay playback with no dialogue, bomb,
//! hit/death, respawn, or time-stop writer. Those omissions are explicit and
//! fail closed where they can enter through the transition input.

pub use zkth06_player_motion::enclosing::PlayerConfig;
use zkth06_player_motion::enclosing::{
    retail_anchor_state, step_enclosing_player, EnclosingError, EnclosingPlayerState,
};
use zkth06_player_motion::{INPUT_FOCUS, PLAYER_STATE_ALIVE, PLAYER_STATE_INVULNERABLE};

pub const INPUT_SHOOT: u16 = 0x0001;
pub const INACTIVE_TIMER_PREVIOUS: i32 = -999;
pub const INACTIVE_TIMER_CURRENT: i32 = -1;
pub const FIRE_TIMER_LIMIT: i32 = 30;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FireBulletTimer {
    pub previous: i32,
    pub current: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ShootingPlayerState {
    pub enclosing: EnclosingPlayerState,
    pub is_focus: bool,
    pub previous_frame_input: u16,
    pub fire_bullet_timer: FireBulletTimer,
    /// Number of `Player::SpawnBullets` calls made since the fixed anchor.
    pub spawn_call_count: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ShootingEffects {
    /// Argument at the `Player::SpawnBullets(player, timer)` call boundary.
    pub spawn_bullets_timer: Option<u8>,
    /// Focus selects which fixed character/shot callback `SpawnBullets` calls.
    pub focused_callback: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ShootingError {
    Enclosing(EnclosingError),
    InvalidFireBulletTimer(FireBulletTimer),
    UnsupportedPlayerState(u8),
    SpawnCounterOverflow,
}

impl From<EnclosingError> for ShootingError {
    fn from(value: EnclosingError) -> Self {
        Self::Enclosing(value)
    }
}

/// First post-calc retail anchor for the no-dialogue shooting profile.
pub fn retail_shooting_anchor_state(
    config: PlayerConfig,
) -> Result<ShootingPlayerState, ShootingError> {
    Ok(ShootingPlayerState {
        enclosing: retail_anchor_state(config)?,
        is_focus: false,
        previous_frame_input: 0,
        fire_bullet_timer: FireBulletTimer {
            previous: INACTIVE_TIMER_PREVIOUS,
            current: INACTIVE_TIMER_CURRENT,
        },
        spawn_call_count: 0,
    })
}

fn validate_timer(timer: FireBulletTimer) -> Result<(), ShootingError> {
    let inactive =
        timer.previous == INACTIVE_TIMER_PREVIOUS && timer.current == INACTIVE_TIMER_CURRENT;
    let active =
        (1..FIRE_TIMER_LIMIT).contains(&timer.current) && timer.previous == timer.current - 1;
    if inactive || active {
        Ok(())
    } else {
        Err(ShootingError::InvalidFireBulletTimer(timer))
    }
}

/// Advances the enclosing Player projection by one gameplay frame.
///
/// Ordering follows the pinned retail callback:
///
/// 1. `Player::OnUpdate` returns immediately during time stop.
/// 2. The enclosing life timer and movement transition executes.
/// 3. `HandlePlayerInputs` derives focus, conditionally starts the fire timer,
///    and stores `previousFrameInput`.
/// 4. `UpdateFireBulletsTimer` emits at most one `SpawnBullets` request, ticks
///    the full-speed timer, and resets it at 30.
///
/// The dialogue gate is fixed false by this profile rather than accepted as
/// private frame input. Active bombs and bomb input are rejected by the
/// enclosing transition.
pub fn step_shooting_player(
    config: PlayerConfig,
    state: ShootingPlayerState,
    input: u16,
) -> Result<(ShootingPlayerState, ShootingEffects), ShootingError> {
    validate_timer(state.fire_bullet_timer)?;
    let retail_state = state.enclosing.life_state.retail_value();
    if retail_state != PLAYER_STATE_ALIVE && retail_state != PLAYER_STATE_INVULNERABLE {
        return Err(ShootingError::UnsupportedPlayerState(retail_state));
    }

    let enclosing = step_enclosing_player(config, state.enclosing, input)?;
    if state.enclosing.is_time_stopped {
        return Ok((
            ShootingPlayerState { enclosing, ..state },
            ShootingEffects {
                spawn_bullets_timer: None,
                focused_callback: state.is_focus,
            },
        ));
    }

    let is_focus = input & INPUT_FOCUS != 0;
    let mut timer = state.fire_bullet_timer;
    if input & INPUT_SHOOT != 0 && timer.current < 0 {
        // `ZunTimer::InitializeForPopup`.
        timer.current = 0;
        timer.previous = INACTIVE_TIMER_PREVIOUS;
    }

    let mut spawn_call_count = state.spawn_call_count;
    let mut spawn_bullets_timer = None;
    if timer.current >= 0 {
        // `HasTicked` is `current != previous`. The validated post-calc state
        // and InitializeForPopup make this true exactly once per active frame.
        if timer.current != timer.previous {
            spawn_bullets_timer = Some(timer.current as u8);
            spawn_call_count = spawn_call_count
                .checked_add(1)
                .ok_or(ShootingError::SpawnCounterOverflow)?;
        }

        // Full-speed `ZunTimer::Tick`: subFrame remains +0 and current gains 1.
        timer.previous = timer.current;
        timer.current += 1;
        if timer.current >= FIRE_TIMER_LIMIT {
            timer.previous = INACTIVE_TIMER_PREVIOUS;
            timer.current = INACTIVE_TIMER_CURRENT;
        }
    }

    Ok((
        ShootingPlayerState {
            enclosing,
            is_focus,
            previous_frame_input: input,
            fire_bullet_timer: timer,
            spawn_call_count,
        },
        ShootingEffects {
            spawn_bullets_timer,
            focused_callback: is_focus,
        },
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use zkth06_player_motion::enclosing::{CHARACTER_REIMU, SHOT_TYPE_A};
    use zkth06_player_motion::{INPUT_BOMB, INPUT_RIGHT};

    fn reimu_a() -> PlayerConfig {
        PlayerConfig {
            character: CHARACTER_REIMU,
            shot_type: SHOT_TYPE_A,
        }
    }

    #[test]
    fn anchor_is_not_witness_supplied() {
        let state = retail_shooting_anchor_state(reimu_a()).unwrap();
        assert_eq!(state.previous_frame_input, 0);
        assert!(!state.is_focus);
        assert_eq!(
            state.fire_bullet_timer,
            FireBulletTimer {
                previous: -999,
                current: -1,
            }
        );
        assert_eq!(state.spawn_call_count, 0);
    }

    #[test]
    fn press_starts_spawns_and_ticks_in_one_frame() {
        let state = retail_shooting_anchor_state(reimu_a()).unwrap();
        let input = INPUT_SHOOT | INPUT_FOCUS | INPUT_RIGHT;
        let (next, effect) = step_shooting_player(reimu_a(), state, input).unwrap();
        assert_eq!(effect.spawn_bullets_timer, Some(0));
        assert!(effect.focused_callback);
        assert_eq!(next.fire_bullet_timer.previous, 0);
        assert_eq!(next.fire_bullet_timer.current, 1);
        assert_eq!(next.spawn_call_count, 1);
        assert!(next.is_focus);
        assert_eq!(next.previous_frame_input, input);
        assert_eq!(next.enclosing.position.x_bits, 194.0_f32.to_bits());
    }

    #[test]
    fn one_press_drives_the_complete_thirty_call_burst() {
        let mut state = retail_shooting_anchor_state(reimu_a()).unwrap();
        let mut observed = [0_u8; FIRE_TIMER_LIMIT as usize];
        for (frame, observed_timer) in observed.iter_mut().enumerate() {
            let input = if frame == 0 { INPUT_SHOOT } else { 0 };
            let (next, effect) = step_shooting_player(reimu_a(), state, input).unwrap();
            *observed_timer = effect.spawn_bullets_timer.unwrap();
            state = next;
        }
        assert_eq!(observed, core::array::from_fn(|index| index as u8));
        assert_eq!(state.fire_bullet_timer.current, INACTIVE_TIMER_CURRENT);
        assert_eq!(state.fire_bullet_timer.previous, INACTIVE_TIMER_PREVIOUS);
        assert_eq!(state.spawn_call_count, 30);

        let (idle, effect) = step_shooting_player(reimu_a(), state, 0).unwrap();
        assert_eq!(effect.spawn_bullets_timer, None);
        assert_eq!(idle.spawn_call_count, 30);
    }

    #[test]
    fn held_shoot_restarts_only_after_the_reset_boundary() {
        let mut state = retail_shooting_anchor_state(reimu_a()).unwrap();
        for expected in 0..30_u8 {
            let (next, effect) = step_shooting_player(reimu_a(), state, INPUT_SHOOT).unwrap();
            assert_eq!(effect.spawn_bullets_timer, Some(expected));
            state = next;
        }
        assert_eq!(state.fire_bullet_timer.current, -1);
        let (next, effect) = step_shooting_player(reimu_a(), state, INPUT_SHOOT).unwrap();
        assert_eq!(effect.spawn_bullets_timer, Some(0));
        assert_eq!(next.fire_bullet_timer.current, 1);
    }

    #[test]
    fn time_stop_precedes_focus_input_and_fire_timer() {
        let mut state = retail_shooting_anchor_state(reimu_a()).unwrap();
        state.enclosing.is_time_stopped = true;
        let (next, effect) =
            step_shooting_player(reimu_a(), state, INPUT_SHOOT | INPUT_FOCUS | INPUT_BOMB).unwrap();
        assert_eq!(next.enclosing.game_frame, state.enclosing.game_frame + 1);
        assert_eq!(next.fire_bullet_timer, state.fire_bullet_timer);
        assert_eq!(next.previous_frame_input, state.previous_frame_input);
        assert_eq!(next.is_focus, state.is_focus);
        assert_eq!(effect.spawn_bullets_timer, None);
    }

    #[test]
    fn malformed_timer_and_overflow_fail_closed() {
        let malformed = ShootingPlayerState {
            fire_bullet_timer: FireBulletTimer {
                previous: 4,
                current: 7,
            },
            ..retail_shooting_anchor_state(reimu_a()).unwrap()
        };
        assert!(matches!(
            step_shooting_player(reimu_a(), malformed, 0),
            Err(ShootingError::InvalidFireBulletTimer(_))
        ));

        let overflow = ShootingPlayerState {
            fire_bullet_timer: FireBulletTimer {
                previous: 0,
                current: 1,
            },
            spawn_call_count: u32::MAX,
            ..retail_shooting_anchor_state(reimu_a()).unwrap()
        };
        assert_eq!(
            step_shooting_player(reimu_a(), overflow, 0),
            Err(ShootingError::SpawnCounterOverflow)
        );
    }
}

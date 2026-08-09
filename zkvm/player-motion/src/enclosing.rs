//! Closed player-position state for the first proof profile.
//!
//! Unlike [`crate::step_position`], this transition does not accept movement
//! parameters per frame.  It derives them from a versioned route
//! configuration and the preceding player state.  The current profile is
//! intentionally limited to full-speed replay playback with no bomb, hit, or
//! ECL time-stop writer.  Unsupported paths fail closed.

use crate::{
    step_position, MotionEnvironment, Position, StepError, INPUT_BOMB, PLAYER_STATE_ALIVE,
    PLAYER_STATE_INVULNERABLE,
};

pub const CHARACTER_REIMU: u8 = 0;
pub const CHARACTER_MARISA: u8 = 1;
pub const SHOT_TYPE_A: u8 = 0;
pub const SHOT_TYPE_B: u8 = 1;

pub const FULL_SPEED_BITS: u32 = 0x3f80_0000;
pub const MOVEMENT_MIN_X_BITS: u32 = 0x4100_0000;
pub const MOVEMENT_MIN_Y_BITS: u32 = 0x4180_0000;
pub const MOVEMENT_SIZE_X_BITS: u32 = 0x43b8_0000;
pub const MOVEMENT_SIZE_Y_BITS: u32 = 0x43d0_0000;
pub const INITIAL_X_BITS: u32 = 0x4340_0000;
pub const INITIAL_Y_BITS: u32 = 0x43c0_0000;
pub const RETAIL_ANCHOR_GAME_FRAME: u32 = 1;
pub const RETAIL_ANCHOR_INVULNERABILITY_TIMER: i32 = 239;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PlayerConfig {
    pub character: u8,
    pub shot_type: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CharacterMotion {
    pub orthogonal_speed_bits: u32,
    pub orthogonal_focus_speed_bits: u32,
    pub diagonal_speed_bits: u32,
    pub diagonal_focus_speed_bits: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PlayerLifeState {
    Alive,
    Invulnerable,
}

impl PlayerLifeState {
    pub const fn retail_value(self) -> u8 {
        match self {
            Self::Alive => PLAYER_STATE_ALIVE,
            Self::Invulnerable => PLAYER_STATE_INVULNERABLE,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EnclosingPlayerState {
    pub game_frame: u32,
    pub position: Position,
    pub life_state: PlayerLifeState,
    pub invulnerability_timer: i32,
    pub is_time_stopped: bool,
    pub bomb_active: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EnclosingError {
    InvalidCharacter(u8),
    InvalidShotType(u8),
    InvalidInvulnerabilityTimer {
        life_state: PlayerLifeState,
        timer: i32,
    },
    UnsupportedBombState,
    UnsupportedBombInput,
    FrameOverflow,
    TimerOverflow,
    Motion(StepError),
}

impl From<StepError> for EnclosingError {
    fn from(value: StepError) -> Self {
        Self::Motion(value)
    }
}

impl PlayerConfig {
    pub fn validate(self) -> Result<Self, EnclosingError> {
        if self.character != CHARACTER_REIMU && self.character != CHARACTER_MARISA {
            return Err(EnclosingError::InvalidCharacter(self.character));
        }
        if self.shot_type != SHOT_TYPE_A && self.shot_type != SHOT_TYPE_B {
            return Err(EnclosingError::InvalidShotType(self.shot_type));
        }
        Ok(self)
    }

    /// Returns the binary32 values stored by retail `Player::AddedCallback`.
    ///
    /// Shot type selects a different source table record, even though the two
    /// records for each character have identical movement values.
    pub fn character_motion(self) -> Result<CharacterMotion, EnclosingError> {
        self.validate()?;
        Ok(match self.character {
            CHARACTER_REIMU => CharacterMotion {
                orthogonal_speed_bits: 0x4080_0000,
                orthogonal_focus_speed_bits: 0x4000_0000,
                diagonal_speed_bits: 0x4035_04f3,
                diagonal_focus_speed_bits: 0x3fb5_04f3,
            },
            CHARACTER_MARISA => CharacterMotion {
                orthogonal_speed_bits: 0x40a0_0000,
                orthogonal_focus_speed_bits: 0x4020_0000,
                diagonal_speed_bits: 0x4061_4213,
                diagonal_focus_speed_bits: 0x3fe1_4213,
            },
            _ => unreachable!(),
        })
    }
}

/// The first post-calc retail anchor, after the pre-game spawn sequence.
///
/// Keeping this constructor fixed avoids admitting an arbitrary initial player
/// state as private witness data.  A later whole-game kernel must derive this
/// anchor from registration and the pre-stage countdown instead.
pub fn retail_anchor_state(config: PlayerConfig) -> Result<EnclosingPlayerState, EnclosingError> {
    config.validate()?;
    Ok(EnclosingPlayerState {
        game_frame: RETAIL_ANCHOR_GAME_FRAME,
        position: Position {
            x_bits: INITIAL_X_BITS,
            y_bits: INITIAL_Y_BITS,
        },
        life_state: PlayerLifeState::Invulnerable,
        invulnerability_timer: RETAIL_ANCHOR_INVULNERABILITY_TIMER,
        is_time_stopped: false,
        bomb_active: false,
    })
}

fn validate_state(state: EnclosingPlayerState) -> Result<(), EnclosingError> {
    let timer_valid = match state.life_state {
        PlayerLifeState::Invulnerable => state.invulnerability_timer > 0,
        PlayerLifeState::Alive => state.invulnerability_timer >= 0,
    };
    if !timer_valid {
        return Err(EnclosingError::InvalidInvulnerabilityTimer {
            life_state: state.life_state,
            timer: state.invulnerability_timer,
        });
    }
    Ok(())
}

fn derive_environment(
    config: PlayerConfig,
    state: EnclosingPlayerState,
) -> Result<MotionEnvironment, EnclosingError> {
    if state.bomb_active {
        return Err(EnclosingError::UnsupportedBombState);
    }
    let motion = config.character_motion()?;
    Ok(MotionEnvironment {
        player_state: state.life_state.retail_value(),
        is_time_stopped: state.is_time_stopped,
        effective_rate_bits: FULL_SPEED_BITS,
        movement_min_x_bits: MOVEMENT_MIN_X_BITS,
        movement_min_y_bits: MOVEMENT_MIN_Y_BITS,
        movement_size_x_bits: MOVEMENT_SIZE_X_BITS,
        movement_size_y_bits: MOVEMENT_SIZE_Y_BITS,
        horizontal_multiplier_bits: FULL_SPEED_BITS,
        vertical_multiplier_bits: FULL_SPEED_BITS,
        orthogonal_speed_bits: motion.orthogonal_speed_bits,
        orthogonal_focus_speed_bits: motion.orthogonal_focus_speed_bits,
        diagonal_speed_bits: motion.diagonal_speed_bits,
        diagonal_focus_speed_bits: motion.diagonal_focus_speed_bits,
    })
}

/// Advances the supported enclosing player state by one gameplay frame.
///
/// The order follows `Player::OnUpdate`: time stop returns first; a bomb would
/// run before the life-state timer and is therefore rejected by this profile;
/// invulnerability is decremented before `HandlePlayerInputs`; movement then
/// uses configuration-derived speeds, bounds, rate, and inactive-bomb factors.
pub fn step_enclosing_player(
    config: PlayerConfig,
    state: EnclosingPlayerState,
    input: u16,
) -> Result<EnclosingPlayerState, EnclosingError> {
    config.validate()?;
    validate_state(state)?;
    let mut next = state;
    next.game_frame = state
        .game_frame
        .checked_add(1)
        .ok_or(EnclosingError::FrameOverflow)?;

    if state.is_time_stopped {
        return Ok(next);
    }
    if state.bomb_active {
        return Err(EnclosingError::UnsupportedBombState);
    }
    if input & INPUT_BOMB != 0 {
        return Err(EnclosingError::UnsupportedBombInput);
    }

    match state.life_state {
        PlayerLifeState::Invulnerable => {
            next.invulnerability_timer -= 1;
            if next.invulnerability_timer == 0 {
                next.life_state = PlayerLifeState::Alive;
            }
        }
        PlayerLifeState::Alive => {
            next.invulnerability_timer = state
                .invulnerability_timer
                .checked_add(1)
                .ok_or(EnclosingError::TimerOverflow)?;
        }
    }

    let environment = derive_environment(config, next)?;
    next.position = step_position(state.position, input, environment)?;
    Ok(next)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::INPUT_RIGHT;

    fn reimu_a() -> PlayerConfig {
        PlayerConfig {
            character: CHARACTER_REIMU,
            shot_type: SHOT_TYPE_A,
        }
    }

    #[test]
    fn fixed_character_records_cover_every_route() {
        for shot_type in [SHOT_TYPE_A, SHOT_TYPE_B] {
            let reimu = PlayerConfig {
                character: CHARACTER_REIMU,
                shot_type,
            }
            .character_motion()
            .unwrap();
            assert_eq!(reimu.diagonal_speed_bits, 0x4035_04f3);

            let marisa = PlayerConfig {
                character: CHARACTER_MARISA,
                shot_type,
            }
            .character_motion()
            .unwrap();
            assert_eq!(marisa.diagonal_speed_bits, 0x4061_4213);
        }
    }

    #[test]
    fn initial_invulnerability_is_derived_until_frame_240() {
        let config = reimu_a();
        let mut state = retail_anchor_state(config).unwrap();
        for _ in 0..238 {
            state = step_enclosing_player(config, state, 0).unwrap();
        }
        assert_eq!(state.game_frame, 239);
        assert_eq!(state.life_state, PlayerLifeState::Invulnerable);
        assert_eq!(state.invulnerability_timer, 1);

        state = step_enclosing_player(config, state, 0).unwrap();
        assert_eq!(state.game_frame, 240);
        assert_eq!(state.life_state, PlayerLifeState::Alive);
        assert_eq!(state.invulnerability_timer, 0);

        state = step_enclosing_player(config, state, 0).unwrap();
        assert_eq!(state.invulnerability_timer, 1);
    }

    #[test]
    fn environment_is_not_a_frame_input() {
        let config = reimu_a();
        let state = retail_anchor_state(config).unwrap();
        let next = step_enclosing_player(config, state, INPUT_RIGHT).unwrap();
        assert_eq!(next.position.x_bits, 196.0_f32.to_bits());
        assert_eq!(next.position.y_bits, 384.0_f32.to_bits());
    }

    #[test]
    fn unsupported_bomb_paths_fail_closed() {
        let config = reimu_a();
        let state = retail_anchor_state(config).unwrap();
        assert_eq!(
            step_enclosing_player(config, state, INPUT_BOMB),
            Err(EnclosingError::UnsupportedBombInput)
        );

        let active = EnclosingPlayerState {
            bomb_active: true,
            ..state
        };
        assert_eq!(
            step_enclosing_player(config, active, 0),
            Err(EnclosingError::UnsupportedBombState)
        );
    }

    #[test]
    fn time_stop_precedes_the_unsupported_bomb_path() {
        let config = reimu_a();
        let stopped = EnclosingPlayerState {
            is_time_stopped: true,
            bomb_active: true,
            ..retail_anchor_state(config).unwrap()
        };
        let next = step_enclosing_player(config, stopped, INPUT_BOMB).unwrap();
        assert_eq!(next.game_frame, stopped.game_frame + 1);
        assert_eq!(next.position, stopped.position);
        assert_eq!(next.invulnerability_timer, stopped.invulnerability_timer);
    }

    #[test]
    fn invalid_configuration_and_state_fail_closed() {
        let state = retail_anchor_state(reimu_a()).unwrap();
        let bad_character = PlayerConfig {
            character: 2,
            shot_type: SHOT_TYPE_A,
        };
        assert_eq!(
            step_enclosing_player(bad_character, state, 0),
            Err(EnclosingError::InvalidCharacter(2))
        );
        let bad_shot = PlayerConfig {
            character: CHARACTER_REIMU,
            shot_type: 2,
        };
        assert_eq!(
            step_enclosing_player(bad_shot, state, 0),
            Err(EnclosingError::InvalidShotType(2))
        );

        let exhausted_invulnerability = EnclosingPlayerState {
            invulnerability_timer: 0,
            ..state
        };
        assert!(matches!(
            step_enclosing_player(reimu_a(), exhausted_invulnerability, 0),
            Err(EnclosingError::InvalidInvulnerabilityTimer { .. })
        ));
        let negative_alive = EnclosingPlayerState {
            life_state: PlayerLifeState::Alive,
            invulnerability_timer: -1,
            ..state
        };
        assert!(matches!(
            step_enclosing_player(reimu_a(), negative_alive, 0),
            Err(EnclosingError::InvalidInvulnerabilityTimer { .. })
        ));
    }

    #[test]
    fn counters_fail_closed_on_overflow() {
        let frame_limit = EnclosingPlayerState {
            game_frame: u32::MAX,
            ..retail_anchor_state(reimu_a()).unwrap()
        };
        assert_eq!(
            step_enclosing_player(reimu_a(), frame_limit, 0),
            Err(EnclosingError::FrameOverflow)
        );

        let timer_limit = EnclosingPlayerState {
            life_state: PlayerLifeState::Alive,
            invulnerability_timer: i32::MAX,
            ..retail_anchor_state(reimu_a()).unwrap()
        };
        assert_eq!(
            step_enclosing_player(reimu_a(), timer_limit, 0),
            Err(EnclosingError::TimerOverflow)
        );
    }
}

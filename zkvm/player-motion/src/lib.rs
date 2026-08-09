#![no_std]
#![forbid(unsafe_code)]

//! Proof-oriented TH06 player-position transition.
//!
//! The API carries every floating-point value as raw binary32 bits. Arithmetic
//! is implemented with integers in [`pc24`] so a future integer-only zkVM guest
//! does not inherit the host's floating-point implementation. The supported
//! domain is deliberately narrow and fails closed outside finite normal values
//! and signed zero.

pub mod pc24;

use core::cmp::Ordering;

use pc24::ArithmeticError;

pub const INPUT_FOCUS: u16 = 0x0004;
pub const INPUT_UP: u16 = 0x0010;
pub const INPUT_DOWN: u16 = 0x0020;
pub const INPUT_LEFT: u16 = 0x0040;
pub const INPUT_RIGHT: u16 = 0x0080;

pub const PLAYER_STATE_ALIVE: u8 = 0;
pub const PLAYER_STATE_INVULNERABLE: u8 = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Position {
    pub x_bits: u32,
    pub y_bits: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MotionEnvironment {
    pub player_state: u8,
    pub is_time_stopped: bool,
    pub effective_rate_bits: u32,
    pub movement_min_x_bits: u32,
    pub movement_min_y_bits: u32,
    pub movement_size_x_bits: u32,
    pub movement_size_y_bits: u32,
    pub horizontal_multiplier_bits: u32,
    pub vertical_multiplier_bits: u32,
    pub orthogonal_speed_bits: u32,
    pub orthogonal_focus_speed_bits: u32,
    pub diagonal_speed_bits: u32,
    pub diagonal_focus_speed_bits: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Parameter {
    EffectiveRate,
    MovementMinX,
    MovementMinY,
    MovementSizeX,
    MovementSizeY,
    HorizontalMultiplier,
    VerticalMultiplier,
    OrthogonalSpeed,
    OrthogonalFocusSpeed,
    DiagonalSpeed,
    DiagonalFocusSpeed,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Axis {
    X,
    Y,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StepError {
    Arithmetic(ArithmeticError),
    UnsupportedPlayerState(u8),
    NegativeParameter(Parameter),
    InvalidBounds(Axis),
}

impl From<ArithmeticError> for StepError {
    fn from(value: ArithmeticError) -> Self {
        Self::Arithmetic(value)
    }
}

/// Advances only the position projection of `Player::OnUpdate`.
///
/// Time stop is handled before the player-state gate, matching the enclosing
/// callback. Outside time stop, only the alive and invulnerable branches call
/// `HandlePlayerInputs`; dead/spawning transitions are rejected because the
/// enclosing callback can write position during respawn.
pub fn step_position(
    position: Position,
    input: u16,
    environment: MotionEnvironment,
) -> Result<Position, StepError> {
    pc24::validate(position.x_bits)?;
    pc24::validate(position.y_bits)?;

    if environment.is_time_stopped {
        return Ok(position);
    }

    if environment.player_state != PLAYER_STATE_ALIVE
        && environment.player_state != PLAYER_STATE_INVULNERABLE
    {
        return Err(StepError::UnsupportedPlayerState(environment.player_state));
    }

    validate_environment(environment)?;

    let (horizontal_speed, vertical_speed) = select_speeds(input, environment)?;
    let horizontal_delta = scale_speed(
        horizontal_speed,
        environment.horizontal_multiplier_bits,
        environment.effective_rate_bits,
    )?;
    let vertical_delta = scale_speed(
        vertical_speed,
        environment.vertical_multiplier_bits,
        environment.effective_rate_bits,
    )?;

    let candidate_x = pc24::add(position.x_bits, horizontal_delta)?;
    let candidate_y = pc24::add(position.y_bits, vertical_delta)?;
    let max_x = pc24::add(
        environment.movement_min_x_bits,
        environment.movement_size_x_bits,
    )?;
    let max_y = pc24::add(
        environment.movement_min_y_bits,
        environment.movement_size_y_bits,
    )?;

    Ok(Position {
        x_bits: clamp(candidate_x, environment.movement_min_x_bits, max_x, Axis::X)?,
        y_bits: clamp(candidate_y, environment.movement_min_y_bits, max_y, Axis::Y)?,
    })
}

fn scale_speed(speed: u32, multiplier: u32, effective_rate: u32) -> Result<u32, StepError> {
    // This operation order is visible in the pinned x87 instruction stream.
    let bomb_scaled = pc24::mul(speed, multiplier)?;
    Ok(pc24::mul(bomb_scaled, effective_rate)?)
}

fn select_speeds(input: u16, environment: MotionEnvironment) -> Result<(u32, u32), StepError> {
    let focused = input & INPUT_FOCUS != 0;
    let orthogonal = if focused {
        environment.orthogonal_focus_speed_bits
    } else {
        environment.orthogonal_speed_bits
    };
    let diagonal = if focused {
        environment.diagonal_focus_speed_bits
    } else {
        environment.diagonal_speed_bits
    };

    let up = input & INPUT_UP != 0;
    let down = input & INPUT_DOWN != 0;
    let left = input & INPUT_LEFT != 0;
    let right = input & INPUT_RIGHT != 0;
    let zero = 0_u32;

    // The ordering is intentional: up wins over down, and right overwrites
    // left within either the vertical or horizontal branch.
    if up {
        if right {
            Ok((diagonal, pc24::negate(diagonal)?))
        } else if left {
            let negative = pc24::negate(diagonal)?;
            Ok((negative, negative))
        } else {
            Ok((zero, pc24::negate(orthogonal)?))
        }
    } else if down {
        if right {
            Ok((diagonal, diagonal))
        } else if left {
            Ok((pc24::negate(diagonal)?, diagonal))
        } else {
            Ok((zero, orthogonal))
        }
    } else if right {
        Ok((orthogonal, zero))
    } else if left {
        Ok((pc24::negate(orthogonal)?, zero))
    } else {
        Ok((zero, zero))
    }
}

fn validate_environment(environment: MotionEnvironment) -> Result<(), StepError> {
    require_non_negative(environment.effective_rate_bits, Parameter::EffectiveRate)?;
    require_non_negative(environment.movement_min_x_bits, Parameter::MovementMinX)?;
    require_non_negative(environment.movement_min_y_bits, Parameter::MovementMinY)?;
    require_non_negative(environment.movement_size_x_bits, Parameter::MovementSizeX)?;
    require_non_negative(environment.movement_size_y_bits, Parameter::MovementSizeY)?;
    require_non_negative(
        environment.horizontal_multiplier_bits,
        Parameter::HorizontalMultiplier,
    )?;
    require_non_negative(
        environment.vertical_multiplier_bits,
        Parameter::VerticalMultiplier,
    )?;
    require_non_negative(
        environment.orthogonal_speed_bits,
        Parameter::OrthogonalSpeed,
    )?;
    require_non_negative(
        environment.orthogonal_focus_speed_bits,
        Parameter::OrthogonalFocusSpeed,
    )?;
    require_non_negative(environment.diagonal_speed_bits, Parameter::DiagonalSpeed)?;
    require_non_negative(
        environment.diagonal_focus_speed_bits,
        Parameter::DiagonalFocusSpeed,
    )?;

    let max_x = pc24::add(
        environment.movement_min_x_bits,
        environment.movement_size_x_bits,
    )?;
    let max_y = pc24::add(
        environment.movement_min_y_bits,
        environment.movement_size_y_bits,
    )?;
    if pc24::compare(environment.movement_min_x_bits, max_x)? == Ordering::Greater {
        return Err(StepError::InvalidBounds(Axis::X));
    }
    if pc24::compare(environment.movement_min_y_bits, max_y)? == Ordering::Greater {
        return Err(StepError::InvalidBounds(Axis::Y));
    }
    Ok(())
}

fn require_non_negative(bits: u32, parameter: Parameter) -> Result<(), StepError> {
    pc24::validate(bits)?;
    if bits & 0x8000_0000 != 0 && bits & 0x7fff_ffff != 0 {
        return Err(StepError::NegativeParameter(parameter));
    }
    Ok(())
}

fn clamp(value: u32, minimum: u32, maximum: u32, axis: Axis) -> Result<u32, StepError> {
    if pc24::compare(minimum, maximum)? == Ordering::Greater {
        return Err(StepError::InvalidBounds(axis));
    }
    if pc24::compare(value, minimum)? == Ordering::Less {
        Ok(minimum)
    } else if pc24::compare(maximum, value)? == Ordering::Less {
        Ok(maximum)
    } else {
        Ok(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reimu_environment() -> MotionEnvironment {
        MotionEnvironment {
            player_state: PLAYER_STATE_ALIVE,
            is_time_stopped: false,
            effective_rate_bits: 1.0_f32.to_bits(),
            movement_min_x_bits: 8.0_f32.to_bits(),
            movement_min_y_bits: 16.0_f32.to_bits(),
            movement_size_x_bits: 368.0_f32.to_bits(),
            movement_size_y_bits: 416.0_f32.to_bits(),
            horizontal_multiplier_bits: 1.0_f32.to_bits(),
            vertical_multiplier_bits: 1.0_f32.to_bits(),
            orthogonal_speed_bits: 4.0_f32.to_bits(),
            orthogonal_focus_speed_bits: 2.0_f32.to_bits(),
            diagonal_speed_bits: 0x4035_04f3,
            diagonal_focus_speed_bits: 0x3fb5_04f3,
        }
    }

    #[test]
    fn cardinal_motion_and_clamp_match_the_source_order() {
        let environment = reimu_environment();
        let start = Position {
            x_bits: 192.0_f32.to_bits(),
            y_bits: 384.0_f32.to_bits(),
        };
        assert_eq!(
            step_position(start, INPUT_RIGHT, environment).unwrap(),
            Position {
                x_bits: 196.0_f32.to_bits(),
                y_bits: 384.0_f32.to_bits(),
            }
        );
        assert_eq!(
            step_position(start, INPUT_UP | INPUT_FOCUS, environment).unwrap(),
            Position {
                x_bits: 192.0_f32.to_bits(),
                y_bits: 382.0_f32.to_bits(),
            }
        );

        let edge = Position {
            x_bits: 376.0_f32.to_bits(),
            y_bits: 16.0_f32.to_bits(),
        };
        assert_eq!(
            step_position(edge, INPUT_RIGHT | INPUT_UP, environment).unwrap(),
            edge
        );
    }

    #[test]
    fn conflicting_bits_follow_retail_priority() {
        let environment = reimu_environment();
        let start = Position {
            x_bits: 192.0_f32.to_bits(),
            y_bits: 384.0_f32.to_bits(),
        };
        let actual = step_position(
            start,
            INPUT_UP | INPUT_DOWN | INPUT_LEFT | INPUT_RIGHT,
            environment,
        )
        .unwrap();
        let diagonal = f32::from_bits(environment.diagonal_speed_bits);
        assert_eq!(actual.x_bits, (192.0_f32 + diagonal).to_bits());
        assert_eq!(actual.y_bits, (384.0_f32 - diagonal).to_bits());
    }

    #[test]
    fn time_stop_precedes_the_player_state_gate() {
        let mut environment = reimu_environment();
        environment.player_state = 2;
        environment.is_time_stopped = true;
        let position = Position {
            x_bits: 192.0_f32.to_bits(),
            y_bits: 384.0_f32.to_bits(),
        };
        assert_eq!(
            step_position(position, INPUT_LEFT, environment),
            Ok(position)
        );

        environment.is_time_stopped = false;
        assert_eq!(
            step_position(position, INPUT_LEFT, environment),
            Err(StepError::UnsupportedPlayerState(2))
        );
    }

    #[test]
    fn unsupported_arithmetic_fails_closed() {
        let environment = reimu_environment();
        let subnormal = Position {
            x_bits: 1,
            y_bits: 384.0_f32.to_bits(),
        };
        assert_eq!(
            step_position(subnormal, 0, environment),
            Err(StepError::Arithmetic(ArithmeticError::SubnormalInput))
        );
    }
}

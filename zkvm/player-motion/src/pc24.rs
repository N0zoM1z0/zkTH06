//! Integer implementation of the finite, normal binary32 subset needed by the
//! TH06 player-position slice under x87 precision-control 24.

use core::cmp::Ordering;

const SIGN_MASK: u32 = 0x8000_0000;
const EXPONENT_MASK: u32 = 0x7f80_0000;
const FRACTION_MASK: u32 = 0x007f_ffff;
const HIDDEN_BIT: u32 = 0x0080_0000;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ArithmeticError {
    NonFiniteInput,
    SubnormalInput,
    ExponentGap,
    SubnormalResult,
    Overflow,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Dyadic {
    negative: bool,
    significand: u32,
    /// `value = (-1)^negative * significand * 2^exponent`.
    exponent: i32,
}

/// Rejects NaN, infinity and subnormal encodings while accepting signed zero.
pub fn validate(bits: u32) -> Result<(), ArithmeticError> {
    decode(bits).map(|_| ())
}

/// Multiplies two supported values and rounds once to a 24-bit significand,
/// round-to-nearest with ties to even.
pub fn mul(left: u32, right: u32) -> Result<u32, ArithmeticError> {
    let left = decode(left)?;
    let right = decode(right)?;
    let negative = left.negative ^ right.negative;
    if left.significand == 0 || right.significand == 0 {
        return Ok(if negative { SIGN_MASK } else { 0 });
    }

    round_dyadic(
        negative,
        u128::from(left.significand) * u128::from(right.significand),
        left.exponent + right.exponent,
    )
}

/// Adds two supported values and rounds once to a 24-bit significand,
/// round-to-nearest with ties to even.
///
/// The player slice never approaches the explicit exponent-gap limit. Keeping
/// the limit checked makes the implementation compact without silently
/// approximating a distant addend.
pub fn add(left: u32, right: u32) -> Result<u32, ArithmeticError> {
    let left = decode(left)?;
    let right = decode(right)?;

    if left.significand == 0 && right.significand == 0 {
        return Ok(if left.negative && right.negative {
            SIGN_MASK
        } else {
            0
        });
    }
    if left.significand == 0 {
        return Ok(encode_exact(right));
    }
    if right.significand == 0 {
        return Ok(encode_exact(left));
    }

    let common_exponent = left.exponent.min(right.exponent);
    let left_shift = u32::try_from(left.exponent - common_exponent).unwrap_or(u32::MAX);
    let right_shift = u32::try_from(right.exponent - common_exponent).unwrap_or(u32::MAX);
    if left_shift > 103 || right_shift > 103 {
        return Err(ArithmeticError::ExponentGap);
    }

    let left_magnitude = i128::from(left.significand) << left_shift;
    let right_magnitude = i128::from(right.significand) << right_shift;
    let signed_left = if left.negative {
        -left_magnitude
    } else {
        left_magnitude
    };
    let signed_right = if right.negative {
        -right_magnitude
    } else {
        right_magnitude
    };
    let exact_sum = signed_left + signed_right;
    if exact_sum == 0 {
        return Ok(0);
    }

    round_dyadic(exact_sum < 0, exact_sum.unsigned_abs(), common_exponent)
}

/// Orders supported finite values exactly. Signed zeros compare equal.
pub fn compare(left: u32, right: u32) -> Result<Ordering, ArithmeticError> {
    let left_decoded = decode(left)?;
    let right_decoded = decode(right)?;
    if left_decoded.significand == 0 && right_decoded.significand == 0 {
        return Ok(Ordering::Equal);
    }
    if left_decoded.negative != right_decoded.negative {
        return Ok(if left_decoded.negative {
            Ordering::Less
        } else {
            Ordering::Greater
        });
    }

    let magnitude_order = (left & !SIGN_MASK).cmp(&(right & !SIGN_MASK));
    Ok(if left_decoded.negative {
        magnitude_order.reverse()
    } else {
        magnitude_order
    })
}

/// Applies the x87 `fchs` sign toggle to a supported value.
pub fn negate(bits: u32) -> Result<u32, ArithmeticError> {
    validate(bits)?;
    Ok(bits ^ SIGN_MASK)
}

fn decode(bits: u32) -> Result<Dyadic, ArithmeticError> {
    let exponent_field = (bits & EXPONENT_MASK) >> 23;
    let fraction = bits & FRACTION_MASK;
    let negative = bits & SIGN_MASK != 0;
    match exponent_field {
        0 if fraction == 0 => Ok(Dyadic {
            negative,
            significand: 0,
            exponent: -149,
        }),
        0 => Err(ArithmeticError::SubnormalInput),
        0xff => Err(ArithmeticError::NonFiniteInput),
        _ => Ok(Dyadic {
            negative,
            significand: HIDDEN_BIT | fraction,
            exponent: exponent_field as i32 - 150,
        }),
    }
}

fn encode_exact(value: Dyadic) -> u32 {
    debug_assert!(value.significand == 0 || value.significand & HIDDEN_BIT != 0);
    if value.significand == 0 {
        return if value.negative { SIGN_MASK } else { 0 };
    }
    let exponent_field = u32::try_from(value.exponent + 150).expect("decoded exponent");
    (if value.negative { SIGN_MASK } else { 0 })
        | (exponent_field << 23)
        | (value.significand & FRACTION_MASK)
}

fn round_dyadic(negative: bool, magnitude: u128, exponent: i32) -> Result<u32, ArithmeticError> {
    if magnitude == 0 {
        return Ok(if negative { SIGN_MASK } else { 0 });
    }

    let bit_length = 128 - magnitude.leading_zeros();
    let (mut significand, mut normalized_exponent) = if bit_length > 24 {
        let shift = bit_length - 24;
        let truncated = magnitude >> shift;
        let discarded_mask = (u128::from(1_u8) << shift) - 1;
        let discarded = magnitude & discarded_mask;
        let halfway = u128::from(1_u8) << (shift - 1);
        let round_up = discarded > halfway || (discarded == halfway && truncated & 1 != 0);
        (
            truncated + u128::from(round_up),
            exponent + i32::try_from(shift).expect("u128 shift fits i32"),
        )
    } else {
        let shift = 24 - bit_length;
        (
            magnitude << shift,
            exponent - i32::try_from(shift).expect("u128 shift fits i32"),
        )
    };

    if significand == (u128::from(1_u8) << 24) {
        significand >>= 1;
        normalized_exponent += 1;
    }

    let exponent_field = normalized_exponent + 150;
    if exponent_field <= 0 {
        return Err(ArithmeticError::SubnormalResult);
    }
    if exponent_field >= 0xff {
        return Err(ArithmeticError::Overflow);
    }
    debug_assert!((u128::from(HIDDEN_BIT)..(u128::from(1_u8) << 24)).contains(&significand));

    Ok((if negative { SIGN_MASK } else { 0 })
        | ((exponent_field as u32) << 23)
        | ((significand as u32) & FRACTION_MASK))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basic_operations_match_binary32() {
        for left in [
            -432.0_f32, -4.0, -0.0, 0.0, 0.5, 1.0, 2.828_427, 192.0, 432.0,
        ] {
            for right in [-4.0_f32, -0.0, 0.0, 0.5, 1.0, 2.0, 5.0] {
                assert_eq!(
                    mul(left.to_bits(), right.to_bits()).unwrap(),
                    (left * right).to_bits(),
                    "{left:?} * {right:?}"
                );
                assert_eq!(
                    add(left.to_bits(), right.to_bits()).unwrap(),
                    (left + right).to_bits(),
                    "{left:?} + {right:?}"
                );
            }
        }
    }

    #[test]
    fn addition_uses_ties_to_even() {
        let one = 1.0_f32.to_bits();
        let half_ulp = (2.0_f32.powi(-24)).to_bits();
        let one_and_a_half_ulp = (3.0_f32 * 2.0_f32.powi(-24)).to_bits();
        assert_eq!(add(one, half_ulp).unwrap(), one);
        assert_eq!(add(one, one_and_a_half_ulp).unwrap(), 0x3f80_0002);
    }

    #[test]
    fn signed_zero_and_exact_cancellation_are_explicit() {
        assert_eq!(add(0x8000_0000, 0x8000_0000).unwrap(), 0x8000_0000);
        assert_eq!(add(0x8000_0000, 0).unwrap(), 0);
        assert_eq!(add(1.0_f32.to_bits(), (-1.0_f32).to_bits()).unwrap(), 0);
        assert_eq!(mul(0, (-1.0_f32).to_bits()).unwrap(), 0x8000_0000);
        assert_eq!(compare(0, 0x8000_0000).unwrap(), Ordering::Equal);
    }

    #[test]
    fn exceptional_classes_fail_closed() {
        assert_eq!(validate(1), Err(ArithmeticError::SubnormalInput));
        assert_eq!(
            validate(f32::INFINITY.to_bits()),
            Err(ArithmeticError::NonFiniteInput)
        );
        assert_eq!(
            validate(f32::NAN.to_bits()),
            Err(ArithmeticError::NonFiniteInput)
        );
    }

    #[test]
    fn deterministic_normal_domain_matches_host_binary32() {
        let mut state = 0x4d59_5df4_d0f3_3173_u64;
        for _ in 0..50_000 {
            state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            let left = ((state as u32) & 0x807f_ffff)
                | (((124 + ((state >> 32) % 9) as u32) & 0xff) << 23);
            state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            let right = ((state as u32) & 0x807f_ffff)
                | (((124 + ((state >> 32) % 9) as u32) & 0xff) << 23);
            let host_left = f32::from_bits(left);
            let host_right = f32::from_bits(right);

            assert_eq!(
                add(left, right).unwrap(),
                (host_left + host_right).to_bits(),
                "add {left:#010x} {right:#010x}"
            );
            assert_eq!(
                mul(left, right).unwrap(),
                (host_left * host_right).to_bits(),
                "mul {left:#010x} {right:#010x}"
            );
            assert_eq!(
                compare(left, right).unwrap(),
                host_left.partial_cmp(&host_right).unwrap(),
                "compare {left:#010x} {right:#010x}"
            );
        }
    }
}

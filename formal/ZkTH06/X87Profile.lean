/-
Copyright (C) 2026 N0zoM1z0

This file decodes the base and D3DX toward-zero x87 control-word profiles found
in the pinned TH06 v1.02h executable. It does not yet define x87 arithmetic or
prove that the Windows loader establishes the base word before game entry.
-/

namespace ZkTH06.X87Profile

abbrev ControlWord := BitVec 16

inductive PrecisionControl where
  | binary24
  | reserved
  | binary53
  | binary64
deriving DecidableEq, Repr

inductive RoundingControl where
  | nearestEven
  | towardNegative
  | towardPositive
  | towardZero
deriving DecidableEq, Repr

def precisionControl (word : ControlWord) : PrecisionControl :=
  match (word.toNat / 0x100) % 4 with
  | 0 => .binary24
  | 1 => .reserved
  | 2 => .binary53
  | _ => .binary64

def roundingControl (word : ControlWord) : RoundingControl :=
  match (word.toNat / 0x400) % 4 with
  | 0 => .nearestEven
  | 1 => .towardNegative
  | 2 => .towardPositive
  | _ => .towardZero

def allExceptionsMasked (word : ControlWord) : Bool :=
  word.toNat % 0x40 == 0x3f

/-- The control word embedded in the target CRT's trigonometric wrappers. -/
def targetControlWord : ControlWord := 0x027f

/-- The target profile with the D3DX helper's toward-zero RC bits applied. -/
def towardZeroControlWord : ControlWord := 0x0e7f

theorem target_precision_is_binary53 :
    precisionControl targetControlWord = .binary53 := by
  decide

theorem target_rounding_is_nearest_even :
    roundingControl targetControlWord = .nearestEven := by
  decide

theorem target_masks_all_six_x87_exceptions :
    allExceptionsMasked targetControlWord = true := by
  decide

theorem toward_zero_profile_preserves_binary53 :
    precisionControl towardZeroControlWord = .binary53 := by
  decide

theorem toward_zero_profile_rounds_toward_zero :
    roundingControl towardZeroControlWord = .towardZero := by
  decide

theorem toward_zero_profile_masks_all_six_x87_exceptions :
    allExceptionsMasked towardZeroControlWord = true := by
  decide

/-- Names for SoftFloat's four directly corresponding rounding modes. -/
inductive SoftFloatRoundingMode where
  | nearEven
  | min
  | max
  | minMag
deriving DecidableEq, Repr

def softFloatRoundingMode : RoundingControl → SoftFloatRoundingMode
  | .nearestEven => .nearEven
  | .towardNegative => .min
  | .towardPositive => .max
  | .towardZero => .minMag

theorem target_softfloat_rounding_mode :
    softFloatRoundingMode (roundingControl targetControlWord) = .nearEven := by
  decide

theorem toward_zero_softfloat_rounding_mode :
    softFloatRoundingMode (roundingControl towardZeroControlWord) = .minMag := by
  decide

/--
Map an x87 precision-control field to SoftFloat's documented
`extF80_roundingPrecision` configuration value.  The SoftFloat value names the
corresponding interchange-format width: 32 means a 24-bit significand, 64
means a 53-bit significand, and 80 means the full 64-bit extended significand.
This is only a configuration correspondence, not an arithmetic-correctness
theorem about SoftFloat or x87.
-/
def softFloatRoundingPrecision : PrecisionControl → Option Nat
  | .binary24 => some 32
  | .reserved => none
  | .binary53 => some 64
  | .binary64 => some 80

theorem target_softfloat_rounding_precision :
    softFloatRoundingPrecision (precisionControl targetControlWord) = some 64 := by
  decide

theorem toward_zero_softfloat_rounding_precision :
    softFloatRoundingPrecision (precisionControl towardZeroControlWord) = some 64 := by
  decide

end ZkTH06.X87Profile

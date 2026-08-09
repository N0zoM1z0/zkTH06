/-
Copyright (C) 2026 N0zoM1z0

This file decodes the x87 control-word profile found in the pinned TH06
v1.02h executable. It does not yet define x87 arithmetic or prove that the
Windows loader establishes this control word before the game entry point.
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

theorem target_precision_is_binary53 :
    precisionControl targetControlWord = .binary53 := by
  decide

theorem target_rounding_is_nearest_even :
    roundingControl targetControlWord = .nearestEven := by
  decide

theorem target_masks_all_six_x87_exceptions :
    allExceptionsMasked targetControlWord = true := by
  decide

end ZkTH06.X87Profile

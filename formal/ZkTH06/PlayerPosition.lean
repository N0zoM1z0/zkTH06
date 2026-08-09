/-
Copyright (C) 2026 N0zoM1z0

This file models the vertical player-position clamp found in the pinned
HandlePlayerInputs body.  It deliberately includes infinities and NaN: the
ordered comparison sequence clamps either infinity but leaves NaN unchanged.
The executable/x87 binding and the proof that each reachable movement
candidate is not NaN remain separate obligations.
-/

import Init.Data.Rat.Lemmas
import Init.Omega

namespace ZkTH06.PlayerPosition

inductive Coordinate where
  | finite (value : Rat)
  | negativeInfinity
  | positiveInfinity
  | nan
deriving DecidableEq, Repr

/-- Ordered lower-then-upper clamp used by the target player update. -/
def clamp (lower upper : Rat) : Coordinate → Coordinate
  | .finite value =>
      if value < lower then .finite lower
      else if upper < value then .finite upper
      else .finite value
  | .negativeInfinity => .finite lower
  | .positiveInfinity => .finite upper
  | .nan => .nan

def finiteBetween (lower upper : Rat) : Coordinate → Prop
  | .finite value => lower ≤ value ∧ value ≤ upper
  | .negativeInfinity | .positiveInfinity | .nan => False

/-- Every non-NaN coordinate, including either infinity, becomes finite and bounded. -/
theorem clamp_bounded_of_not_nan
    (lower upper : Rat) (candidate : Coordinate)
    (orderedBounds : lower ≤ upper) (notNan : candidate ≠ .nan) :
    finiteBetween lower upper (clamp lower upper candidate) := by
  cases candidate with
  | finite value =>
      simp only [clamp]
      split <;> rename_i belowLower
      · exact ⟨Rat.le_refl, orderedBounds⟩
      · split <;> rename_i aboveUpper
        · exact ⟨orderedBounds, Rat.le_refl⟩
        · exact ⟨Rat.not_lt.mp belowLower, Rat.not_lt.mp aboveUpper⟩
  | negativeInfinity => exact ⟨Rat.le_refl, orderedBounds⟩
  | positiveInfinity => exact ⟨orderedBounds, Rat.le_refl⟩
  | nan => simp at notNan

def movementCandidate
    (position speed bombMultiplier frameMultiplier : Rat) : Coordinate :=
  .finite (position + speed * bombMultiplier * frameMultiplier)

def movementStepY
    (position speed bombMultiplier frameMultiplier : Rat) : Coordinate :=
  clamp 16 432 (movementCandidate position speed bombMultiplier frameMultiplier)

/-- The mathematical finite-input movement core re-establishes the player-y invariant. -/
theorem movement_step_y_bounded
    (position speed bombMultiplier frameMultiplier : Rat) :
    finiteBetween 16 432
      (movementStepY position speed bombMultiplier frameMultiplier) := by
  apply clamp_bounded_of_not_nan
  · native_decide
  · simp [movementCandidate]

def initialY : Coordinate := .finite 384
def respawnY : Coordinate := .finite 384

theorem initial_y_bounded : finiteBetween 16 432 initialY := by
  simp only [initialY, finiteBetween]
  have lower : (16 : Int) ≤ 384 := by omega
  have upper : (384 : Int) ≤ 432 := by omega
  exact ⟨Rat.intCast_le_intCast.mpr lower, Rat.intCast_le_intCast.mpr upper⟩

theorem respawn_y_bounded : finiteBetween 16 432 respawnY := by
  simp only [respawnY, finiteBetween]
  have lower : (16 : Int) ≤ 384 := by omega
  have upper : (384 : Int) ≤ 432 := by omega
  exact ⟨Rat.intCast_le_intCast.mpr lower, Rat.intCast_le_intCast.mpr upper⟩

def grabTopY (center : Rat) : Rat := center - 12
def grabBottomY (center : Rat) : Rat := center + 12

/-- A bounded finite center produces the decoded radius-12 grab interval. -/
theorem bounded_center_grab_box
    (center : Rat) (lower : (16 : Rat) ≤ center) (upper : center ≤ (432 : Rat)) :
    (4 : Rat) ≤ grabTopY center ∧
      grabTopY center ≤ (420 : Rat) ∧
      (28 : Rat) ≤ grabBottomY center ∧
      grabBottomY center ≤ (444 : Rat) := by
  have topLower : (4 : Rat) ≤ center - 12 := by
    have shifted :=
      (Rat.add_le_add_right (a := (16 : Rat)) (b := center) (c := (-12 : Rat))).2
        lower
    have constant : (16 : Rat) + (-12 : Rat) = 4 := by native_decide
    rw [constant] at shifted
    simpa [Rat.sub_eq_add_neg] using shifted
  have topUpper : center - 12 ≤ (420 : Rat) := by
    have shifted :=
      (Rat.add_le_add_right (a := center) (b := (432 : Rat)) (c := (-12 : Rat))).2
        upper
    have constant : (432 : Rat) + (-12 : Rat) = 420 := by native_decide
    rw [constant] at shifted
    simpa [Rat.sub_eq_add_neg] using shifted
  have bottomLower : (28 : Rat) ≤ center + 12 := by
    have shifted :=
      (Rat.add_le_add_right (a := (16 : Rat)) (b := center) (c := (12 : Rat))).2
        lower
    have constant : (16 : Rat) + 12 = 28 := by native_decide
    rw [constant] at shifted
    exact shifted
  have bottomUpper : center + 12 ≤ (444 : Rat) := by
    have shifted :=
      (Rat.add_le_add_right (a := center) (b := (432 : Rat)) (c := (12 : Rat))).2
        upper
    have constant : (432 : Rat) + 12 = 444 := by native_decide
    rw [constant] at shifted
    exact shifted
  exact ⟨topLower, topUpper, bottomLower, bottomUpper⟩

end ZkTH06.PlayerPosition

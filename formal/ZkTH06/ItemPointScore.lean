/-
Copyright (C) 2026 N0zoM1z0

This file isolates the geometry and point-item score formula suggested by the
pinned ItemManager blocks.  The first lemmas expose the finite integer core;
the later total model adds exact rational finite coordinates, infinities, and
NaN.  Entry into either model still requires separate binary32/x87, collision,
helper-path, and code-binding proofs.  In particular, AABB success alone does
not exclude NaN.
-/

import Init.Data.Rat.Lemmas
import Init.Omega

namespace ZkTH06.ItemPointScore

inductive Profile where
  | easyNormal
  | hard
  | lunatic
  | extra
deriving DecidableEq, Repr

def topScore : Profile → Int
  | .easyNormal => 100000
  | .hard => 150000
  | .lunatic => 200000
  | .extra => 300000

def bottomScore : Profile → Int
  | .easyNormal => 60000
  | .hard => 100000
  | .lunatic => 150000
  | .extra => 200000

def positionMultiplier : Profile → Int
  | .easyNormal => 100
  | .hard => 180
  | .lunatic => 270
  | .extra => 400

/-- Integer score formula after both helper calls have been refined to one value. -/
def score (profile : Profile) (truncatedY : Int) : Int :=
  if truncatedY < 128 then
    topScore profile
  else
    bottomScore profile - ((truncatedY - 128) * positionMultiplier profile)

/-- Ordered one-dimensional part of the 12-radius player/8-half-size item AABB test. -/
def orderedCollectionOverlapY (playerY itemY : Int) : Prop :=
  ¬ (playerY - 12 > itemY + 8 ∨ playerY + 12 < itemY - 8)

/-- Player y in 16..432 and ordered overlap imply item y in -4..452. -/
theorem ordered_collection_bounds_item_y
    (playerY itemY : Int)
    (playerLower : 16 ≤ playerY)
    (playerUpper : playerY ≤ 432)
    (overlap : orderedCollectionOverlapY playerY itemY) :
    -4 ≤ itemY ∧ itemY ≤ 452 := by
  simp [orderedCollectionOverlapY] at overlap
  omega

/-- Every profile's mathematical score stays in a small positive interval. -/
theorem bounded_score_range
    (profile : Profile) (truncatedY : Int)
    (lower : -4 ≤ truncatedY) (upper : truncatedY ≤ 452) :
    27600 ≤ score profile truncatedY ∧ score profile truncatedY ≤ 300000 := by
  cases profile <;>
    simp [score, topScore, bottomScore, positionMultiplier] <;>
    omega

/-- Consequently the selected score and its penalty arithmetic fit signed i32. -/
theorem bounded_score_fits_signed_i32
    (profile : Profile) (truncatedY : Int)
    (lower : -4 ≤ truncatedY) (upper : truncatedY ≤ 452) :
    -(2 ^ 31 : Int) ≤ score profile truncatedY ∧
      score profile truncatedY < (2 ^ 31 : Int) := by
  have bounded := bounded_score_range profile truncatedY lower upper
  omega

/-- On the lower branch, the position delta and worst multiplier remain small. -/
theorem bounded_position_penalty
    (profile : Profile) (truncatedY : Int)
    (lowerBranch : 128 ≤ truncatedY) (upper : truncatedY ≤ 452) :
    0 ≤ (truncatedY - 128) * positionMultiplier profile ∧
      (truncatedY - 128) * positionMultiplier profile ≤ 129600 := by
  cases profile <;> simp [positionMultiplier] <;> omega

/-- The source frame cap plus one bounded item award cannot wrap the u32 score. -/
theorem bounded_gameplay_score_addition
    (profile : Profile) (truncatedY gameScore : Int)
    (yLower : -4 ≤ truncatedY) (yUpper : truncatedY ≤ 452)
    (scoreLower : 0 ≤ gameScore) (scoreUpper : gameScore ≤ 999999999) :
    0 ≤ gameScore + score profile truncatedY ∧
      gameScore + score profile truncatedY < (2 ^ 32 : Int) := by
  have itemBounded := bounded_score_range profile truncatedY yLower yUpper
  omega

/-!
The following model restores exceptional coordinates instead of assuming that
every collected item is finite.  A finite binary32 value is an exact dyadic
rational, so `Rat` is sufficient for the geometric part.  The exceptional
constructors model the ordered x87 comparison classes relevant to the vertical
AABB test.  `observedTrunc` maps exceptional conversion to zero because masked
invalid `fistp` stores integer-indefinite and the audited callers observe EAX.
The executable/control-word binding for those premises remains separate.
-/

inductive Coordinate where
  | finite (value : Rat)
  | negativeInfinity
  | positiveInfinity
  | nan
deriving DecidableEq, Repr

/-- Truncation toward zero for an exact finite rational. -/
def truncTowardZero (value : Rat) : Int :=
  if 0 ≤ value then value.floor else value.ceil

/-- The vertical separation disjunction with a finite player center. -/
def verticallySeparated (playerY : Rat) : Coordinate → Prop
  | .finite itemY => playerY - 12 > itemY + 8 ∨ playerY + 12 < itemY - 8
  | .negativeInfinity | .positiveInfinity => True
  | .nan => False

def collectedY (playerY : Rat) (itemY : Coordinate) : Prop :=
  ¬ verticallySeparated playerY itemY

/-- Low-EAX observation of the helper in the modeled coordinate classes. -/
def observedTrunc : Coordinate → Int
  | .finite value => truncTowardZero value
  | .negativeInfinity | .positiveInfinity | .nan => 0

/-- Exact rational overlap gives the finite item-center interval. -/
theorem finite_collection_bounds_item_y
    (playerY itemY : Rat)
    (playerLower : (16 : Rat) ≤ playerY)
    (playerUpper : playerY ≤ (432 : Rat))
    (overlap : ¬ (playerY - 12 > itemY + 8 ∨ playerY + 12 < itemY - 8)) :
    (-4 : Rat) ≤ itemY ∧ itemY ≤ (452 : Rat) := by
  simp only [not_or] at overlap
  have lowerOverlap : playerY - 12 ≤ itemY + 8 :=
    Rat.not_lt.mp overlap.left
  have upperOverlap : itemY - 8 ≤ playerY + 12 :=
    Rat.not_lt.mp overlap.right
  constructor
  · have playerShifted : (4 : Rat) ≤ playerY - 12 := by
      have shifted :=
        (Rat.add_le_add_right (a := (16 : Rat)) (b := playerY) (c := (-12 : Rat))).2
          playerLower
      have constant : (16 : Rat) + (-12 : Rat) = 4 := by native_decide
      rw [constant] at shifted
      simpa [Rat.sub_eq_add_neg] using shifted
    have itemShifted : (4 : Rat) ≤ itemY + 8 :=
      Rat.le_trans playerShifted lowerOverlap
    have shifted :=
      (Rat.add_le_add_right (a := (4 : Rat)) (b := itemY + 8) (c := (-8 : Rat))).2
        itemShifted
    have constant : (4 : Rat) + (-8 : Rat) = -4 := by native_decide
    rw [constant] at shifted
    have cancel : itemY + 8 + (-8 : Rat) = itemY := by
      rw [← Rat.sub_eq_add_neg]
      exact Rat.add_sub_cancel
    rw [cancel] at shifted
    exact shifted
  · have playerShifted : playerY + 12 ≤ (444 : Rat) := by
      have shifted :=
        (Rat.add_le_add_right (a := playerY) (b := (432 : Rat)) (c := (12 : Rat))).2
          playerUpper
      have constant : (432 : Rat) + 12 = 444 := by native_decide
      rw [constant] at shifted
      exact shifted
    have itemShifted : itemY - 8 ≤ (444 : Rat) :=
      Rat.le_trans upperOverlap playerShifted
    have shifted :=
      (Rat.add_le_add_right (a := itemY - 8) (b := (444 : Rat)) (c := (8 : Rat))).2
        itemShifted
    have constant : (444 : Rat) + 8 = 452 := by native_decide
    rw [constant] at shifted
    simpa [Rat.sub_add_cancel] using shifted

/-- Truncation toward zero preserves the score-relevant rational interval. -/
theorem trunc_toward_zero_bounds
    (value : Rat)
    (lower : (-4 : Rat) ≤ value)
    (upper : value ≤ (452 : Rat)) :
    -4 ≤ truncTowardZero value ∧ truncTowardZero value ≤ 452 := by
  simp only [truncTowardZero]
  split <;> rename_i sign
  · constructor
    · exact Rat.le_floor_iff.mpr lower
    · have upperIntCast : value ≤ ((452 : Int) : Rat) := by simpa using upper
      have bounded := Rat.floor_monotone upperIntCast
      have constant : (((452 : Int) : Rat).floor) = (452 : Int) :=
        Rat.floor_intCast 452
      rw [constant] at bounded
      exact bounded
  · constructor
    · have castBound : ((-4 : Int) : Rat) ≤ ((value.ceil : Int) : Rat) :=
        Rat.le_trans lower Rat.le_ceil
      exact Rat.intCast_le_intCast.mp castBound
    · have upperIntCast : value ≤ ((452 : Int) : Rat) := by simpa using upper
      exact Rat.ceil_le_iff.mpr upperIntCast

/--
Collected score is bounded for every modeled coordinate class.  Infinities
cannot overlap a finite player box; NaN may overlap but its invalid helper
projection is zero and therefore selects the top-score branch.
-/
theorem collected_score_range_without_item_finiteness
    (profile : Profile) (playerY : Rat) (itemY : Coordinate)
    (playerLower : (16 : Rat) ≤ playerY)
    (playerUpper : playerY ≤ (432 : Rat))
    (collected : collectedY playerY itemY) :
    27600 ≤ score profile (observedTrunc itemY) ∧
      score profile (observedTrunc itemY) ≤ 300000 := by
  cases itemY with
  | finite value =>
      have rationalBounds := finite_collection_bounds_item_y
        playerY value playerLower playerUpper collected
      have integerBounds := trunc_toward_zero_bounds
        value rationalBounds.left rationalBounds.right
      exact bounded_score_range profile (truncTowardZero value)
        integerBounds.left integerBounds.right
  | negativeInfinity => simp [collectedY, verticallySeparated] at collected
  | positiveInfinity => simp [collectedY, verticallySeparated] at collected
  | nan =>
      cases profile <;>
        simp [observedTrunc, score, topScore]

/-- The total coordinate theorem also prevents one capped gameplay-score addition from wrapping. -/
theorem collected_gameplay_score_addition_without_item_finiteness
    (profile : Profile) (playerY : Rat) (itemY : Coordinate) (gameScore : Int)
    (playerLower : (16 : Rat) ≤ playerY)
    (playerUpper : playerY ≤ (432 : Rat))
    (collected : collectedY playerY itemY)
    (scoreLower : 0 ≤ gameScore) (scoreUpper : gameScore ≤ 999999999) :
    0 ≤ gameScore + score profile (observedTrunc itemY) ∧
      gameScore + score profile (observedTrunc itemY) < (2 ^ 32 : Int) := by
  have itemBounded := collected_score_range_without_item_finiteness
    profile playerY itemY playerLower playerUpper collected
  omega

end ZkTH06.ItemPointScore

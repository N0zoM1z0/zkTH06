/-
Copyright (C) 2026 N0zoM1z0

This file isolates the integer geometry and point-item score formula suggested
by the pinned ItemManager blocks.  Coordinates are already mathematical
integers here: entry into this model requires a separate proof that the
binary32 positions are finite/ordered and that __ftol2 yields the modeled
integer.  In particular, AABB success alone does not exclude NaN.
-/

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

end ZkTH06.ItemPointScore

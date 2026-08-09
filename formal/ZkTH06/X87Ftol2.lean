/-
Copyright (C) 2026 N0zoM1z0

This file isolates the integer correction and register projection used by the
target's __ftol2 helper.  The case assumptions are proof obligations for the
future arithmetic semantics; this file does not establish them for raw x87
encodings or reachable TH06 states.
-/

import Std.Tactic.BVDecide

namespace ZkTH06.X87Ftol2

inductive Sign where
  | nonnegative
  | negative
deriving DecidableEq, Repr

/-- Position of the nearest-even integer relative to truncation toward zero. -/
inductive NearestCase where
  | exact
  | towardZero
  | awayFromZero
deriving DecidableEq, Repr

def nearestInteger (sign : Sign) (case : NearestCase) (truncated : Int) : Int :=
  match case with
  | .exact | .towardZero => truncated
  | .awayFromZero =>
      match sign with
      | .nonnegative => truncated + 1
      | .negative => truncated - 1

/-- Integer effect of the two carry/borrow correction paths in __ftol2. -/
def correctedInteger
    (sign : Sign) (case : NearestCase) (nearest : Int) : Int :=
  match case with
  | .exact | .towardZero => nearest
  | .awayFromZero =>
      match sign with
      | .nonnegative => nearest - 1
      | .negative => nearest + 1

theorem correction_recovers_truncation
    (sign : Sign) (case : NearestCase) (truncated : Int) :
    correctedInteger sign case (nearestInteger sign case truncated) = truncated := by
  cases sign <;> cases case <;> simp [correctedInteger, nearestInteger]

abbrev I64Bits := BitVec 64
abbrev Register32 := BitVec 32

def eax (result : I64Bits) : Register32 :=
  result.extractLsb' 0 32

def edx (result : I64Bits) : Register32 :=
  result.extractLsb' 32 32

def joinRegisters (high low : Register32) : I64Bits :=
  high.append low

theorem edx_eax_reconstruct_result (result : I64Bits) :
    joinRegisters (edx result) (eax result) = result := by
  simp only [joinRegisters, edx, eax]
  bv_decide

/-- The mapped game consumers project the helper result to EAX (or AL). -/
def observedLow32 (result : I64Bits) : Register32 := eax result

theorem high_half_irrelevant_to_observed_projection
    (highA highB low : Register32) :
    observedLow32 (joinRegisters highA low) =
      observedLow32 (joinRegisters highB low) := by
  simp only [observedLow32, joinRegisters, eax]
  bv_decide

end ZkTH06.X87Ftol2

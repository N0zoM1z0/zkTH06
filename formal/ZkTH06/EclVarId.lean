/-
Copyright (C) 2026 N0zoM1z0

This file isolates the observation made by the mapped GetVarFloat caller of
__ftol2.  It models the contiguous switch labels in the pinned reconstruction;
it does not prove source/binary correspondence or ext80 truncation semantics.
-/

import Std.Tactic.BVDecide

namespace ZkTH06.EclVarId

def firstVariableId : Int := -10025
def lastVariableId : Int := -10001

/-- The 25 integer labels handled by GetVar after GetVarFloat truncation. -/
def isVariableId (truncated : Int) : Bool :=
  decide (firstVariableId ≤ truncated ∧ truncated ≤ lastVariableId)

def decodeVariableId (truncated : Int) : Option Int :=
  if isVariableId truncated then some truncated else none

abbrev Word32 := BitVec 32

/-- The exact unsigned add/compare predicate decoded at `0x0040afd0..0x0040afdc`. -/
def machineIsVariableId (word : Word32) : Bool :=
  (word + 10025).ule 24

/--
The wrapping add followed by an unsigned comparison recognizes exactly the
signed 32-bit encodings from -10025 through -10001.  This proves the finite
instruction-level predicate, not that the executable bytes decode to it.
-/
theorem machine_classifier_matches_signed_interval (word : Word32) :
    machineIsVariableId word =
      ((-10025 : Word32).sle word && word.sle (-10001 : Word32)) := by
  simp only [machineIsVariableId]
  bv_decide

inductive Resolution (Literal : Type) where
  | variable (id : Int)
  | literal (value : Literal)
deriving DecidableEq, Repr

/-- Source-level observation after conversion: a switch label or the original literal. -/
def resolve (truncated : Int) (literal : Literal) : Resolution Literal :=
  match decodeVariableId truncated with
  | some id => .variable id
  | none => .literal literal

theorem first_variable_id_is_recognized :
    isVariableId firstVariableId = true := by
  decide

theorem last_variable_id_is_recognized :
    isVariableId lastVariableId = true := by
  decide

theorem adjacent_ids_are_not_recognized :
    isVariableId (firstVariableId - 1) = false ∧
      isVariableId (lastVariableId + 1) = false := by
  decide

def declaredVariableIds : List Int :=
  (List.range 25).map fun offset => lastVariableId - Int.ofNat offset

theorem declared_variable_id_count : declaredVariableIds.length = 25 := by
  decide

theorem every_declared_variable_id_is_recognized :
    declaredVariableIds.all isVariableId = true := by
  decide

/-- Outside the 25 labels, the numeric conversion result is not otherwise observed. -/
theorem nonvariable_result_returns_original_literal
    (truncated : Int) (literal : Literal)
    (outside : isVariableId truncated = false) :
    resolve truncated literal = .literal literal := by
  simp [resolve, decodeVariableId, outside]

/-- Any two non-label truncation results induce the same source-level resolution. -/
theorem nonvariable_integer_value_is_irrelevant
    (a b : Int) (literal : Literal)
    (aOutside : isVariableId a = false)
    (bOutside : isVariableId b = false) :
    resolve a literal = resolve b literal := by
  simp [resolve, decodeVariableId, aOutside, bOutside]

end ZkTH06.EclVarId

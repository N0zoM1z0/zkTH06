/-
Copyright (C) 2026 N0zoM1z0

This file models the narrow ECL writer-policy observation used by the sealed
retail-data audit.  Typed writers respect GetVar's readonly classification;
opcodes 18 and 19 increment or decrement the returned pointer directly.  The
artifact-to-decoder, handler, and fixed-data bindings remain separate proof
obligations.
-/

namespace ZkTH06.EclPlayerWrite

inductive WriterPolicy where
  | noOutput
  | typed
  | unchecked
deriving DecidableEq, Repr

def writerPolicy (opcode : Nat) : WriterPolicy :=
  if opcode = 18 ∨ opcode = 19 then .unchecked
  else if opcode = 3 ∨ (4 ≤ opcode ∧ opcode ≤ 17) ∨ (20 ≤ opcode ∧ opcode ≤ 26) then
    .typed
  else
    .noOutput

def playerXId : Int := -10018
def playerYId : Int := -10019
def playerZId : Int := -10020

def playerPositionIds : List Int := [playerXId, playerYId, playerZId]

/--
The modeled typed handlers cannot write player y because GetVar reports it as
readonly.  Only an unchecked handler with exactly the player-y ID may do so.
-/
def mayWritePlayerY (opcode : Nat) (destination : Int) : Prop :=
  writerPolicy opcode = .unchecked ∧ destination = playerYId

theorem writer_policy_unchecked_iff (opcode : Nat) :
    writerPolicy opcode = .unchecked ↔ opcode = 18 ∨ opcode = 19 := by
  by_cases unchecked : opcode = 18 ∨ opcode = 19
  · simp [writerPolicy, unchecked]
  · by_cases typed :
        opcode = 3 ∨ (4 ≤ opcode ∧ opcode ≤ 17) ∨ (20 ≤ opcode ∧ opcode ≤ 26)
    · simp [writerPolicy, unchecked, typed]
    · simp [writerPolicy, unchecked, typed]

theorem typed_writer_cannot_write_player_y
    (opcode : Nat) (typed : writerPolicy opcode = .typed) :
    ¬mayWritePlayerY opcode playerYId := by
  intro writes
  exact WriterPolicy.noConfusion (typed.symm.trans writes.1)

theorem player_y_write_requires_unchecked_opcode
    {opcode : Nat} {destination : Int}
    (writes : mayWritePlayerY opcode destination) :
    (opcode = 18 ∨ opcode = 19) ∧ destination = playerYId := by
  exact ⟨(writer_policy_unchecked_iff opcode).mp writes.1, writes.2⟩

/-- Destination support of all 80 unchecked writes in the pinned seven ECL files. -/
def retailUncheckedDestinationSupport : List Int := [-10012, -10004, -10002, -10001]

theorem retail_unchecked_support_excludes_player_position :
    ∀ destination ∈ retailUncheckedDestinationSupport,
      destination ∉ playerPositionIds := by
  simp [retailUncheckedDestinationSupport, playerPositionIds, playerXId, playerYId, playerZId]

end ZkTH06.EclPlayerWrite

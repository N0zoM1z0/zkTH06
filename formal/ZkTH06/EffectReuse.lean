/-
Copyright (C) 2026 N0zoM1z0

This file models one narrow allocation phase observed in the pinned TH06
reference. It is not a model of the whole EffectManager or game transition.
-/

namespace ZkTH06.EffectReuse

/-- Raw IEEE-754 binary32 storage. No arithmetic interpretation is assumed. -/
abbrev F32Bits := BitVec 32

/-- Pointer-free storage for the three binary32 words of a reference vector. -/
structure Vec3Bits where
  x : F32Bits
  y : F32Bits
  z : F32Bits
deriving DecidableEq, Repr

inductive EffectKind where
  | other
  | spellOrbit
deriving DecidableEq, Repr

/--
The fields needed for the spell-orbit reuse argument. In the reference,
`SpawnParticles` activates a free slot and overwrites `pos1`; the ECL caller
overwrites `pos2`; `unk_15c` and `angleRelated` survive from the free slot.
-/
structure EffectSlot where
  active : Bool
  kind : EffectKind
  pos1 : Vec3Bits
  pos2 : Vec3Bits
  radius : F32Bits
  angle : F32Bits
deriving DecidableEq, Repr

structure LiveEffect where
  kind : EffectKind
  pos1 : Vec3Bits
  pos2 : Vec3Bits
  radius : F32Bits
  angle : F32Bits
deriving DecidableEq, Repr

def EffectSlot.live (slot : EffectSlot) : LiveEffect :=
  { kind := slot.kind
    pos1 := slot.pos1
    pos2 := slot.pos2
    radius := slot.radius
    angle := slot.angle }

/-- Revision-0.2's problematic abstraction: a free slot has no state. -/
def projectActiveOnly (slot : EffectSlot) : Option LiveEffect :=
  if slot.active then some slot.live else none

/--
One-slot abstraction of the reference allocation phase. An occupied slot is
skipped. A free spell-orbit slot receives new positions but retains its radius
and angle residue.
-/
def spawnSpellOrbit (pos1 pos2 : Vec3Bits) (slot : EffectSlot) : EffectSlot :=
  if slot.active then
    slot
  else
    { slot with
      active := true
      kind := .spellOrbit
      pos1 := pos1
      pos2 := pos2 }

/-- A projection that retains exactly the dormant residue used by this model. -/
inductive EffectProjection where
  | dormant (radius angle : F32Bits)
  | live (effect : LiveEffect)
deriving DecidableEq, Repr

def projectWithShadow (slot : EffectSlot) : EffectProjection :=
  if slot.active then
    .live slot.live
  else
    .dormant slot.radius slot.angle

/-- The projected allocation step, defined without access to omitted state. -/
def kernelSpawnSpellOrbit (pos1 pos2 : Vec3Bits) : EffectProjection → EffectProjection
  | .live effect => .live effect
  | .dormant radius angle =>
      .live
        { kind := .spellOrbit
          pos1 := pos1
          pos2 := pos2
          radius := radius
          angle := angle }

/-- The dormant reuse shadow makes this allocation phase commute exactly. -/
theorem project_spawnSpellOrbit
    (slot : EffectSlot) (pos1 pos2 : Vec3Bits) :
    projectWithShadow (spawnSpellOrbit pos1 pos2 slot) =
      kernelSpawnSpellOrbit pos1 pos2 (projectWithShadow slot) := by
  cases h : slot.active <;>
    simp [spawnSpellOrbit, projectWithShadow, kernelSpawnSpellOrbit, h,
      EffectSlot.live]

private def zeroVec : Vec3Bits := { x := 0, y := 0, z := 0 }

private def dormantZero : EffectSlot :=
  { active := false
    kind := .other
    pos1 := zeroVec
    pos2 := zeroVec
    radius := 0
    angle := 0 }

private def dormantOne : EffectSlot :=
  { dormantZero with radius := 1 }

/-- Active-only projection aliases two free slots with different future state. -/
theorem activeOnly_collision :
    projectActiveOnly dormantZero = projectActiveOnly dormantOne := by
  rfl

/-- The same spell allocation exposes the dormant difference. -/
theorem activeOnly_post_spawn_diverges :
    projectActiveOnly (spawnSpellOrbit zeroVec zeroVec dormantZero) ≠
      projectActiveOnly (spawnSpellOrbit zeroVec zeroVec dormantOne) := by
  decide

/-- A concrete counterexample to active-only one-step noninterference. -/
theorem activeOnly_noninterference_fails :
    ∃ s₁ s₂,
      projectActiveOnly s₁ = projectActiveOnly s₂ ∧
      projectActiveOnly (spawnSpellOrbit zeroVec zeroVec s₁) ≠
        projectActiveOnly (spawnSpellOrbit zeroVec zeroVec s₂) := by
  exact ⟨dormantZero, dormantOne, activeOnly_collision,
    activeOnly_post_spawn_diverges⟩

/-- The reuse-shadow projection separates the counterexample states. -/
theorem shadow_separates_counterexample :
    projectWithShadow dormantZero ≠ projectWithShadow dormantOne := by
  decide

end ZkTH06.EffectReuse

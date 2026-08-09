/-
Copyright (C) 2026 N0zoM1z0

This file specifies the x87 condition-code observations consumed by the 244
mapped TH06 comparison branches.  It checks the masks and branches found by
the static audit; it does not prove the disassembly reachable or the hardware
comparison correct.
-/

namespace ZkTH06.X87Compare

inductive Relation where
  | greater
  | less
  | equal
  | unordered
deriving DecidableEq, Repr

structure ConditionCodes where
  c0 : Bool
  c2 : Bool
  c3 : Bool
deriving DecidableEq, Repr

/-- FCOM/FCOMP's documented C0/C2/C3 encoding. -/
def conditionCodes : Relation → ConditionCodes
  | .greater => ⟨false, false, false⟩
  | .less => ⟨true, false, false⟩
  | .equal => ⟨false, false, true⟩
  | .unordered => ⟨true, true, true⟩

inductive StatusFilter where
  | andEax100
  | andEax4100
  | testAh1
  | testAh5
  | testAh41
  | testAh44
deriving DecidableEq, Repr

inductive ConditionalBranch where
  | je
  | jne
  | jp
  | jnp
deriving DecidableEq, Repr

/-- Condition bits selected by the six masks present in mapped game code. -/
def selectedBits : StatusFilter → ConditionCodes → List Bool
  | .andEax100, codes => [codes.c0]
  | .andEax4100, codes => [codes.c0, codes.c3]
  | .testAh1, codes => [codes.c0]
  | .testAh5, codes => [codes.c0, codes.c2]
  | .testAh41, codes => [codes.c0, codes.c3]
  | .testAh44, codes => [codes.c2, codes.c3]

def zeroFlag (bits : List Bool) : Bool :=
  bits.all (!·)

/-- x86 PF is even parity over the low result byte. -/
def parityFlag (bits : List Bool) : Bool :=
  bits.count true % 2 == 0

def branchTaken
    (filter : StatusFilter) (branch : ConditionalBranch)
    (relation : Relation) : Bool :=
  let bits := selectedBits filter (conditionCodes relation)
  match branch with
  | .je => zeroFlag bits
  | .jne => !zeroFlag bits
  | .jp => parityFlag bits
  | .jnp => !parityFlag bits

def relations : List Relation := [.greater, .less, .equal, .unordered]

def truthTable
    (filter : StatusFilter) (branch : ConditionalBranch) : List Bool :=
  relations.map (branchTaken filter branch)

-- Order in every table is greater, less, equal, unordered.
theorem and_100_je_table :
    truthTable .andEax100 .je = [true, false, true, false] := by
  decide

theorem and_100_jne_table :
    truthTable .andEax100 .jne = [false, true, false, true] := by
  decide

theorem and_4100_je_table :
    truthTable .andEax4100 .je = [true, false, false, false] := by
  decide

theorem and_4100_jne_table :
    truthTable .andEax4100 .jne = [false, true, true, true] := by
  decide

theorem test_1_jne_table :
    truthTable .testAh1 .jne = [false, true, false, true] := by
  decide

theorem test_41_jne_table :
    truthTable .testAh41 .jne = [false, true, true, true] := by
  decide

theorem test_41_jp_table :
    truthTable .testAh41 .jp = [true, false, false, true] := by
  decide

theorem test_44_jnp_table :
    truthTable .testAh44 .jnp = [false, false, true, false] := by
  decide

theorem test_44_jp_table :
    truthTable .testAh44 .jp = [true, true, false, true] := by
  decide

theorem test_5_jnp_table :
    truthTable .testAh5 .jnp = [false, true, false, false] := by
  decide

theorem test_5_jp_table :
    truthTable .testAh5 .jp = [true, false, true, true] := by
  decide

inductive OperandClass where
  | zero
  | subnormal
  | normal
  | infinity
  | quietNaN
  | signalingNaN
deriving DecidableEq, Repr

def isNaN : OperandClass → Bool
  | .quietNaN | .signalingNaN => true
  | _ => false

def isSubnormal : OperandClass → Bool
  | .subnormal => true
  | _ => false

/-- FCOM treats every NaN as invalid before considering #D. -/
def invalidException (a b : OperandClass) : Bool :=
  isNaN a || isNaN b

def denormalException (a b : OperandClass) : Bool :=
  !invalidException a b && (isSubnormal a || isSubnormal b)

theorem quiet_nan_is_invalid_for_fcom :
    invalidException .quietNaN .normal = true := by
  decide

theorem invalid_suppresses_denormal_operand :
    denormalException .quietNaN .subnormal = false := by
  decide

end ZkTH06.X87Compare

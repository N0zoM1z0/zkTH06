/-
Copyright (C) 2026 N0zoM1z0

This file records the finite-input denormal-operand predicates exercised by
the x87/SoftFloat probe.  It machine-checks the shape of the discovered
exception-priority counterexamples; it does not prove that a processor or
SoftFloat implements these predicates.
-/

namespace ZkTH06.X87Exceptions

inductive MagnitudeClass where
  | zero
  | subnormal
  | normal
deriving DecidableEq, Repr

structure FiniteOperand where
  negative : Bool
  magnitude : MagnitudeClass
deriving DecidableEq, Repr

inductive BasicOperation where
  | add
  | sub
  | mul
  | div
  | sqrt
deriving DecidableEq, Repr

inductive BoundaryOperation where
  | storeF32
  | storeF64
  | frndint
  | fistI32
  | fistI64
deriving DecidableEq, Repr

def isZero (operand : FiniteOperand) : Bool :=
  operand.magnitude == .zero

def isSubnormal (operand : FiniteOperand) : Bool :=
  operand.magnitude == .subnormal

/-- The rejected rule: classify only by the presence of a subnormal operand. -/
def naiveArithmeticDenormal
    (operation : BasicOperation) (a b : FiniteOperand) : Bool :=
  match operation with
  | .sqrt => isSubnormal a
  | _ => isSubnormal a || isSubnormal b

/--
Finite-input predicate used by the current differential harness.  For the
tested register divide form, a zero divisor takes priority over denormal input.
For square root, a negative finite nonzero input takes invalid-operation
priority.  The remaining binary operations signal on either subnormal input.
-/
def arithmeticDenormal
    (operation : BasicOperation) (a b : FiniteOperand) : Bool :=
  match operation with
  | .div => (isSubnormal a || isSubnormal b) && !isZero b
  | .sqrt => isSubnormal a && !a.negative
  | _ => isSubnormal a || isSubnormal b

/-- FSTP/FISTP do not define #D for these forms; FRNDINT does. -/
def boundaryDenormal
    (operation : BoundaryOperation) (a : FiniteOperand) : Bool :=
  match operation with
  | .frndint => isSubnormal a
  | _ => false

def positiveZero : FiniteOperand := ⟨false, .zero⟩
def positiveSubnormal : FiniteOperand := ⟨false, .subnormal⟩
def negativeSubnormal : FiniteOperand := ⟨true, .subnormal⟩

theorem naive_divide_zero_counterexample :
    naiveArithmeticDenormal .div positiveSubnormal positiveZero = true ∧
    arithmeticDenormal .div positiveSubnormal positiveZero = false := by
  decide

theorem naive_negative_sqrt_counterexample :
    naiveArithmeticDenormal .sqrt negativeSubnormal positiveZero = true ∧
    arithmeticDenormal .sqrt negativeSubnormal positiveZero = false := by
  decide

theorem frndint_positive_subnormal_signals_denormal :
    boundaryDenormal .frndint positiveSubnormal = true := by
  decide

theorem stores_and_fist_do_not_signal_denormal (operand : FiniteOperand) :
    boundaryDenormal .storeF32 operand = false ∧
    boundaryDenormal .storeF64 operand = false ∧
    boundaryDenormal .fistI32 operand = false ∧
    boundaryDenormal .fistI64 operand = false := by
  simp [boundaryDenormal]

end ZkTH06.X87Exceptions

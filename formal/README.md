# Formal refinement plan

This directory is reserved for the machine-checked argument that the sliced
zkTH06 gameplay kernel preserves the relevant behavior of the pinned reference
transition. No theorem is implemented or claimed yet.

## Target theorem shape

Let:

- `RefState` be the state of the pinned, authoritative transition;
- `KernelState` be the smaller state represented inside the zkVM;
- `Input` be the complete per-frame input mask;
- `project : RefState -> KernelState` remove presentation-only state;
- `refStep : RefState -> Input -> RefState` preserve authentic calc-chain order;
- `kernelStep : KernelState -> Input -> KernelState` be the zkTH06 transition;
- `Inv : RefState -> Prop` describe the reachable-state invariant.

The central one-frame refinement obligation is:

```text
Inv s -> kernelStep (project s) i = project (refStep s i)
```

The corresponding noninterference or quotient obligation is:

```text
Inv s1 -> Inv s2 -> project s1 = project s2 ->
  project (refStep s1 i) = project (refStep s2 i)
```

It says that state removed by `project` cannot affect the next projected state.
This is the proof obligation behind every rendering, audio, animation, message,
or effect-state deletion.

Additional obligations are:

1. the canonical initial state satisfies `Inv`;
2. `refStep` preserves `Inv`;
3. the terminal and acceptance predicates agree through `project`;
4. replay stage boundaries are derived transitions, not trusted resets; and
5. arithmetic operations have the exact overflow, rounding, and exceptional
   behavior named by the theorem.

Induction over the input list then yields whole-run projected trace and terminal
equivalence.

## Proof-oriented implementation rules

- Canonical state is pointer-free, has fixed-width fields, fixed-capacity arrays,
  and explicit active-slot indices.
- A frame is split into named calc phases. Each phase has a pure state/input
  boundary even if the compatibility runner still mutates C++ globals.
- Removed state receives a dependency record and a noninterference lemma; it is
  not deleted solely because corpus runs still finish.
- Disabled or inactive storage is not treated uniformly: an uninitialized field
  is excluded when its control mode makes it unreadable, while dormant residue
  is retained whenever allocation can expose it before overwrite.
- Integer overflow and shifts use bit-vector semantics. Floating-point values
  retain raw bits until an exact model or a proved refinement replaces them.
- Script positions use stable identifiers or base-relative offsets, never host
  pointers.
- The schema digest, reference source revision, data manifest, and proof source
  revision are public inputs or build metadata of the final statement.
- Production theorems may not depend on `sorry`, unreviewed axioms, or empirical
  replay assumptions.

## Binding the theorem to code

Proving a handwritten Lean model does not by itself prove the C++ reference or
the zkVM guest. The project still has to choose and audit a binding method, such
as a restricted source subset with translation validation, generation of both
an executable kernel and Lean semantics from one definition, or a verified
compiler path. Differential traces remain valuable for finding model and
translation bugs, but are not a substitute for this binding.

The immediate engineering consequence is to extract small, deterministic,
side-effect-explicit subsystem steps before freezing either the Lean model or
the guest. Tool selection comes after the canonical state and arithmetic
experiments make the required source subset concrete.

The live field/reuse audit is in
[`../docs/state-projection-audit.md`](../docs/state-projection-audit.md). Its
first intended owner-local lemmas cover enemy template overwrite, canonical
zeroed enemy bullets, item state-2 target initialization, guarded ANM
interpolation, dormant Effect reuse, and dynamic screen-effect noninterference.

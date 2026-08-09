# Formal refinement plan

This directory contains the beginning of the machine-checked argument that the
sliced zkTH06 gameplay kernel preserves the relevant behavior of the pinned
reference transition. One owner-local Effect allocation model is checked; no
whole-frame, whole-game, or C++-binding theorem is claimed.

[`ZkTH06/X87Profile.lean`](ZkTH06/X87Profile.lean) separately decodes the
`0x027f` control word embedded in the pinned executable's CRT trigonometric
wrappers. It checks 53-bit significand precision, round-to-nearest-even, and
six masked x87 exceptions. It also checks that this precision field selects
SoftFloat's documented `extF80_roundingPrecision = 64` configuration. The same
file decodes `0x0e7f`, produced when the audited D3DX helpers set toward-zero,
and checks its mapping to SoftFloat's minimum-magnitude rounding mode. These
are profile/configuration facts only: they neither implement x87 operations
nor prove SoftFloat equivalent to x87 or establish the Windows loader's entry
word.

[`ZkTH06/X87Exceptions.lean`](ZkTH06/X87Exceptions.lean) records the
finite-input denormal-operand predicate exercised by the differential probe. It
checks counterexamples to the rejected "any subnormal input" rule for divide
by zero and negative square root, and distinguishes `frndint` from the tested
`fstp`/`fistp` boundaries. This is a machine-checked classification model, not
a proof of the Intel/AMD manuals, hardware, SoftFloat, or the assembly harness.

[`ZkTH06/X87Compare.lean`](ZkTH06/X87Compare.lean) records the
greater/less/equal/unordered C0/C2/C3 encoding and evaluates the eleven
`fnstsw` mask/branch signatures found at all 244 mapped comparison sites. It
also records FCOM's invalid-before-denormal priority for NaN inputs. These are
finite truth tables attached to the static evidence, not a reachability or
binary-decoding theorem.

[`ZkTH06/X87Ftol2.lean`](ZkTH06/X87Ftol2.lean) checks that the helper's
nearest-integer carry/borrow correction recovers truncation toward zero in all
sign/rounding-position cases. It also proves the EDX:EAX split/join identity
and that a low-32-bit observer is independent of EDX. For the architectural
integer-indefinite constant `0x8000000000000000`, it proves EAX is zero and EDX
is `0x80000000`. The unproved premises remain substantial: raw ext80 decoding,
the masked-invalid `fistp` semantics and entry control state, site-specific
range or observation safety for every reachable call, correspondence with the
117 extracted bytes, and replacement of the bounded no-EDX-observer scan with
complete control-flow evidence.

[`ZkTH06/EclVarId.lean`](ZkTH06/EclVarId.lean) isolates the observation made
by the retained `EnemyEclInstr::GetVarFloat` call. It proves with `bv_decide`
that the decoded 32-bit wrapping add and unsigned comparison recognize exactly
the signed encodings `-10025..-10001`, and proves that all non-label integer
results return the same original literal in the abstract resolver. This removes
the need for an arbitrary signed-32-bit range premise from the desired
site-specific theorem. It does not prove that the executable decodes to the
model, that `__ftol2` implements the classifier for all reachable ext80 inputs,
that jump targets have the modeled meanings, or that the guest refines it.

[`ZkTH06/PlayerPosition.lean`](ZkTH06/PlayerPosition.lean) totalizes the
retail vertical clamp over exact finite rationals, both infinities, and NaN.
`clamp_bounded_of_not_nan` proves that every non-NaN candidate---including
either infinity---becomes finite in `16..432`; NaN alone survives the two
ordered-comparison branches. It also checks the modeled initial and respawn
center `384`, a finite mathematical movement step, and the radius-12 grab-box
ranges `4..420` and `28..444`. These are consequences of the model. The
instruction decode, binary32/x87 behavior, writer completeness, movement
candidate not-NaN invariant, update ordering, source correspondence, and guest
binding remain explicit obligations in the associated audit artifact.

[`ZkTH06/ItemPointScore.lean`](ZkTH06/ItemPointScore.lean) models the four
retained point-item score profiles after conversion to mathematical integers.
Given player `y` in `16..432` and an ordered one-dimensional AABB overlap with
the decoded radii 12 and 8, it derives item `y` in `-4..452`. It then proves all
four scores lie in `27600..300000`, fit signed i32, and have lower-branch
penalty at most 129600. Given the source frame cap `score ≤ 999999999`, it also
proves one item addition cannot wrap u32. A second model represents finite
binary32 values exactly as rationals alongside both infinities and NaN. It
proves a total score bound without assuming item finiteness: infinities cannot
overlap a finite bounded player box, while NaN's modeled invalid conversion has
low EAX zero and selects the top-score branch. `X87Ftol2.lean` separately
checks the integer-indefinite EDX:EAX split. Entering this total model still
requires the player artifact's candidate-not-NaN/writer/scheduling premises,
binary32/x87, collision-code, helper-path, and source/binary binding proofs.

The address-level bridge to these definitions is
[`arithmetic/obligations-v1.json`](../arithmetic/obligations-v1.json). Its 244
comparison records name one of the eleven `X87Compare` truth-table theorems;
its 77 helper records name the `X87Ftol2` projection/correction contracts. The
ledger is deliberately not imported as a Lean axiom or theorem. All site slice
statuses and helper range claims remain open until a later generated semantics
or translation-validation layer produces checked correspondence evidence.

## Checked Effect reuse result

[`ZkTH06/EffectReuse.lean`](ZkTH06/EffectReuse.lean) models the specific
spell-orbit allocation behavior found in the reference: a free Effect slot
receives new positions while its radius and angle residue survive. It proves:

1. two dormant slots can collide under an active-only projection;
2. the same allocation exposes their different residue, giving a concrete
   counterexample to one-step noninterference; and
3. retaining the dormant radius/angle shadow makes this narrowly modeled
   allocation step commute with a projected kernel step.

The model treats floats as `BitVec 32`; it proves copying and projection facts,
not floating-point arithmetic. Build the pinned Lean 4.32.0 project with:

```sh
cd formal
lake build
```

The development contains no `sorry`, admitted theorem, or custom axiom. Its
field scope is deliberately smaller than the full `Effect` structure, so the
commuting theorem is not yet evidence that radius and angle alone form a
sufficient full-game reuse shadow.

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
The address-level arithmetic evidence and the proposed binary-to-IR binding are
in [`../docs/arithmetic-audit.md`](../docs/arithmetic-audit.md).

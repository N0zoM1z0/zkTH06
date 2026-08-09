# zkVM guest boundary

This directory is reserved for zkTH06-owned proof code: the versioned gameplay
transition, witness/public-input schema, acceptance predicate and backend
adapters.

No guest is frozen yet. M0 must first produce frame-identical canonical state
digests between the shipped v1.02h behavior and the adapted runner. Encoding a
known-divergent Linux simulation in a zkVM would prove the wrong semantics more
efficiently, so guest implementation starts only after that differential gate.

The intended boundary is:

- public: target/version commitments, kernel revision, route and initial-state
  commitment, input commitment, terminal claim;
- private: frame inputs and any authenticated data-opening material;
- derived inside the guest: every gameplay state transition, stage boundary,
  resource counter, RNG step and terminal acceptance condition.

Replay stage snapshots are compatibility inputs only. They must eventually be
ignored or constrained against state derived from the preceding stage.

## Refinement boundary

The guest is intended to be a proof-oriented slice, not an independently
rewritten simulator. Its state projection and subsystem steps must support a
machine-checked commuting diagram:

```text
       authoritative state  --reference frame--> authoritative state
               |                                      |
            project                                project
               |                                      |
               v                                      v
          kernel state       --kernel frame-->    kernel state
```

Every removed field needs a noninterference argument showing that two valid
reference states with the same projection produce the same next projection.
The planned Lean obligations, code-binding problem, and no-`sorry` policy are
tracked in [`../formal/README.md`](../formal/README.md). Replay differential
tests are the counterexample finder for this theorem, not its proof.

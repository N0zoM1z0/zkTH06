# zkVM kernel and guest boundary

This directory contains zkTH06-owned proof code: sliced gameplay transitions
now, and eventually the witness/public-input schema, acceptance predicate and
backend adapters.

[`player-motion/`](player-motion/) is the first frozen microkernel. It advances
only the Player x/y position projection for alive or invulnerable frames. All
floating-point values enter and leave as raw `u32` bits; integer code performs
each multiply, add, ordered comparison and binary32 store using a 24-bit
significand and round-to-nearest-even. The implementation rejects non-finite or
subnormal operands and results, overflow, unsupported exponent gaps, and player
states whose enclosing callback can respawn-write position.

The microkernel matches 1,999 consecutive transitions extracted from the first
2,000-frame shipped-executable anchor. That establishes an executable
translation-validation target for one projection. It does not freeze or claim
a complete zkVM guest, whole-Player semantics, whole-state equivalence, or a
formal source/binary refinement proof.

[`player-shooting/`](player-shooting/) is the next enclosing layer. It reuses
the frozen motion/life transition and derives focus, previous input, fire-timer
start/tick/reset state, and `SpawnBullets` requests. A retail-bound `ZKSHV1`
vector checks 1,999 consecutive transitions and 1,590 callback requests.
[`player-shooting-openvm/`](player-shooting-openvm/) proves the same transition
with only replay masks as per-frame private input. This layer ends at callback
dispatch.

[`player-bullets/`](player-bullets/) refines one Reimu-A callback through the
80-slot allocator and initialized raw geometry for ranks 1--3. The companion
[`player-bullets-openvm/`](player-bullets-openvm/) guest proves 1,590 observed
calls and hashes all 422 initialized outputs. Its input includes a complete
pre-call slot-state array for each call. Those arrays are retail-bound but
independently observed, so this layer is a local function proof rather than an
enclosing multi-frame bullet state machine. Bullet motion, ANM termination,
slot reclamation, and Enemy collision remain the next linkage obligation.

[`player-bullet-lifecycle/`](player-bullet-lifecycle/) links that state through
frame 207, and [`early-gameplay/`](early-gameplay/) composes the first real
Enemy collision at frame 208. [`first-wave/`](first-wave/) then carries every
fired and collided slot through all five first-wave deaths at frame 229.
[`first-wave-openvm/`](first-wave-openvm/) proves the full 228-transition chain
from the fixed frame-1 anchor using only replay masks. The successor
[`first-item/`](first-item/) derives the death-drop cursor, small-power Item
spawn and raw-bit movement, collection geometry, collision-ANM reclamation,
and retained score/power/subrank writes through frame 249.
[`first-item-openvm/`](first-item-openvm/) proves all 248 transitions from the
same anchor with a 520-byte replay-only input. It fails closed before the next
Enemy/ECL, RNG, and Enemy-bullet state is composed. [`second-wave/`](second-wave/)
then derives that next timeline group through frame 350: six spawns, five
deaths, ECL movement, death-effect RNG, two random drops, score, and an
explicitly retained empty Enemy-bullet pool. [`second-wave-openvm/`](second-wave-openvm/)
replays the complete chain from frame 1 using only 350 private input masks and
commits every incremental frame-250--350 projection. It fails closed at the
first unsupported surviving ECL-time/trigonometric path; the next extension
must reach the first active Enemy bullets observed at frame 1180.

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

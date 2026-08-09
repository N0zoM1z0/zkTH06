# Player-position microkernel

This `no_std` crate implements the first narrow zkTH06 transition:

```text
(previous raw x/y, replay input, raw movement environment)
    -> next raw x/y
```

It follows the pinned `Player::OnUpdate`/`HandlePlayerInputs` order: time-stop
gate, alive/invulnerable gate, retail direction priority, focus-speed choice,
horizontal and vertical bomb multipliers, effective-rate multiplication, and
the two ordered movement-area clamps. Each arithmetic instruction rounds to a
24-bit significand using round-to-nearest-even. Explicit binary32 stores are
therefore exact within the accepted normal finite domain.

The target function begins at `0x00427860`; the audited movement arithmetic and
clamps occupy `0x00427da2..0x00427eb8`. The static address/signature evidence is
retained separately in
[`../../arithmetic/player-position-v1.json`](../../arithmetic/player-position-v1.json),
so this crate does not treat the reconstructed C++ expression alone as the
binary contract.

The crate intentionally uses no host floating-point operations outside tests.
[`src/pc24.rs`](src/pc24.rs) decodes raw binary32 values as integer dyadics,
performs exact intermediate integer arithmetic, and rounds explicitly. Values
outside the current proved/tested domain fail closed instead of being
approximated. Both the original environment-record adapter and the stronger
enclosing-state adapter execute this same crate in OpenVM.

[`src/enclosing.rs`](src/enclosing.rs) is the current stateful boundary. For a
fixed character/shot configuration it constructs the first post-calc anchor
and derives each next life state, invulnerability timer, carried time-stop and
bomb flags, character speeds, full-speed rate, movement bounds, and inactive-
bomb multipliers before calling the arithmetic slice. Its supported profile is
deliberately `full-speed-no-bomb-no-hit-no-time-stop-write`; bomb input/active
bombs and invalid state/timer combinations fail closed. Time stop returns
before the bomb/timer/movement path, matching the audited retail ordering.

Run the pinned toolchain tests with:

```sh
cd zkvm
cargo test --workspace
```

The integration test consumes
[`../../evidence/player-motion-002677-2000-v1.bin`](../../evidence/player-motion-002677-2000-v1.bin).
Its 120-byte little-endian `ZKPMV1` header binds the target executable, replay,
and sealed retail trace hashes. Each 68-byte record contains the frame index,
input, gate state, raw movement environment, previous position, and expected
next position. The 2,000 source frames yield 1,999 consecutive transitions.

A second integration test consumes
[`../../evidence/player-state-002677-2000-v1.bin`](../../evidence/player-state-002677-2000-v1.bin).
It reconstructs the fixed anchor and checks all reached state/timer/position
words across the same 1,999 transitions without supplying a per-frame motion
environment. The retail/source signature bridge for this stateful profile is
[`../../arithmetic/player-state-enclosing-v1.json`](../../arithmetic/player-state-enclosing-v1.json).

The remaining soundness obligations are explicit:

- bind the mapped retail instruction sequence and PC24 control state to this
  operation order;
- prove the integer dyadic implementation implements the accepted x87/binary32
  subset;
- prove the domain checks hold for every reachable claimed frame, or enlarge
  the exact arithmetic semantics;
- derive the fixed post-calc anchor from registration and pre-stage scheduling;
- prove complete writer exclusion for the profile's life state, timer,
  time-stop, bomb, rate, bounds, and speed data;
- implement collision/death/respawn, bomb callbacks, external time-stop writes,
  and non-full-speed timers before enlarging the profile; and
- bind the Rust code compiled for the eventual zkVM to the same transition
  relation.

The retained vector is finite counterexample-search evidence, not any of those
proofs.

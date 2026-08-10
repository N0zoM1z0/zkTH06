# M0 replay differential runner progress

Last updated: 2026-08-10

## Implemented

- Standalone strict v1.02h replay validation with `--replay-info`.
- Bounds-checked decoded stage views and a playback cursor capped by the first
  valid `9999999` sentinel.
- Direct headless compatibility playback with `--replay`.
- An address-bound Wine/GDB retail probe that verifies the pinned executable
  and DAT hashes, normalizes a pre-game Wine timing artifact, selects one
  replay in an isolated runtime directory, and samples the instruction after
  `Chain::RunCalcChain`.
- Complete replay masks (Shoot, Bomb, Focus, Skip and four directions) injected
  by the existing ReplayManager at calc priority 5.
- Replay deaths, bombs and respawns continue rather than using the RL harness's
  first-hit terminal.
- Deterministic terminal summaries and `replay-complete` detection.
- Canonical trace revision 0.2 with a fixed 592-byte frame record, eleven
  domain-separated subsystem digests, raw binary32 encoding, stable entity
  indices, relative script offsets, and fail-closed output handling.
- Real selected-field serializers for gameplay, ECL, Stage, GUI/message, and
  future-live owner-local ANM state, plus an independent Python validator,
  first-mismatch comparator, and payload statistics.
- A Lean 4.32.0 owner-local Effect model that checks the active-only reuse
  counterexample and a commuting allocation step with a narrow dormant shadow.
- A hash-bound static arithmetic audit that attributes x87 sites and calls to
  mapped functions, distinguishes XMM-bearing CRT/D3DX code, and emits a
  path-free JSON summary; plus a checked Lean decode of control word `0x027f`.
- A reproducible, commit-pinned Berkeley SoftFloat Release 3e differential
  probe for x87 results and six exception bits, covering basic arithmetic,
  binary32/binary64 stores, `frndint`, and signed 32/64-bit `fistp` across
  nearest-even and toward-zero profiles, plus DWORD/QWORD `fcomp` condition
  codes and canonical NaN/denormal priority cases.
- A checked finite-input Lean model of the rejected naive denormal rule and the
  instruction-specific predicate exercised by that probe.
- An exact-byte, temporary i386 harness for the pinned `__ftol2` body, an
  independent dyadic truncation model, and Lean checks of its correction and
  EDX:EAX projection logic; a 37-instruction helper audit and sampled masked-
  invalid integer-indefinite result now expose the low-EAX exceptional quotient.
- A source/sink candidate ledger for all 77 helper calls, a pinned 25-way ECL
  dispatch audit, and a Lean bit-vector theorem for its wrapping-add/unsigned-
  compare classifier. Every correspondence and omission remains explicitly
  unproved.
- A pinned four-profile point-item score audit covering eight helper calls and
  77 key instruction roles, plus total rational/exceptional Lean score bounds
  and a sealed 2,081-collection Linux corpus report. A dependent player-position
  audit checks 95 more instruction roles and a total Lean clamp theorem. Item
  finiteness is no longer a premise, and either infinity is clamped; the player
  proof is now reduced to candidate-not-NaN, writer, scheduling, binary/x87,
  and guest bindings rather than assumed closed. A fixed-data ECL audit walks
  8,384 subroutine instructions and rules out player-position outputs among
  1,844 writer candidates, including all 80 type-guard-bypassing
  increment/decrement operations,
  conditional on extraction/decoder/handler bindings.
- A `no_std`, integer-only player-position microkernel that carries binary32
  values as raw bits, implements the observed PC24 multiply/add/clamp order with
  explicit round-to-nearest-even, and fails closed outside its finite
  normal/zero and alive/invulnerable domain. A compact retail-derived vector
  checks 1,999 consecutive transitions bit for bit.
- A standalone OpenVM v2.0.1 RV32IM guest that calls that same crate, uses the
  native SHA-256 extension to bind the complete private workload and computed
  endpoint into all 32 public-value bytes, and has a tracked application proof,
  verifying key, vm executable, exact commitment descriptor, and path-free
  performance/source-binding manifest.
- A fail-closed enclosing player-state transition for the full-speed/no-bomb/
  no-hit/no-time-stop-write profile. It fixes the post-calc anchor and derives
  life state, invulnerability timer, time-stop carry, character speeds,
  movement bounds, rate, and inactive-bomb multipliers from preceding state
  and one character/shot configuration rather than per-frame witness words.
- A 55-instruction, 30-source-anchor static audit for that enclosing
  transition, a 40-field retail/reference comparison, a 1,999-transition state
  vector, and a second tracked OpenVM application proof whose private
  per-frame record is only the replay input mask.
- A shooting-cadence refinement that derives focus, previous input, fire-timer
  start/tick/reset state, and `SpawnBullets` call requests. A 54-instruction,
  33-source-anchor audit, 46-field retail/reference comparison, 1,999-step
  vector with 1,590 callback requests, and third tracked OpenVM proof bind this
  layer through focused/unfocused callback dispatch.
- A local Reimu-A bullet-spawn refinement for power ranks 1--3. An address-bound
  retail hook and reference trace compare complete 80-slot pre/post state,
  dormant carry, initialized geometry/timers, and the ANM request projection at
  1,590 calls. A 56-instruction/31-source-anchor static audit, fixed-width
  vector, Rust transition, and fourth OpenVM application proof cover all 422
  initialized bullets without host floating point or trigonometry.
- An enclosing Reimu-A rank-1 Player/bullet lifecycle through the first
  external collision. A 50-field retail/reference oracle, 29-instruction/
  31-source-anchor static audit, linked vector, integer-only Rust transition,
  and fifth OpenVM application proof derive 206 consecutive transitions from
  the fixed frame-1 empty pool using replay masks only. The guest derives 173
  spawn calls, 35 initializations, and 30 bounds reclamations, then fails
  closed before EnemyManager's first collided-state write at frame 208.

Compatibility playback intentionally restores every per-stage replay snapshot,
matching shipped playback. It is an oracle-development mode, not the future
canonical-proof mode.

## First retail executable anchor

The first shipped-executable comparison uses the tracked Normal Reimu A
no-miss/no-bomb replay (`01bc11b...ad10f`). The retail side runs Japanese TH06
v1.02h (`9f76483c...52245`) under Wine 11.0 and stops at `0x00420858`, the
instruction immediately after `Chain::RunCalcChain`. The Linux trace is written
at the corresponding return boundary. Across frames 1--2,000, the complete
50-field lifecycle projection matches semantically:

- route, stage, frame, replay input, and Supervisor state;
- RNG seed and generation count;
- score, lives, bombs, deaths, bombs used, retries, power, rank, and subrank;
- Player state, time-stop state, and raw binary32 x/y/z bits;
- the raw effective-framerate multiplier, movement-area bounds, and bomb
  movement multipliers;
- all four character movement-speed records; and
- the configured framerate multiplier, respawn timer, active-bomb flag, and
  invulnerability timer previous/subframe/current words; and
- GUI current-message state, Player focus and previous input, and fire-timer
  previous/subframe/current words; and
- the structured `Player::SpawnBullets` entry/exit projection when a callback
  occurs, including all 80 slot states and active bullet details; and
- `UpdatePlayerBullets` before/after and post-frame pool projections, plus the
  last-enemy-hit target used by the type-1 route.

This interval exercises 27 distinct input masks, advances RNG generation from
2 to 3,555, and reaches score 767,990. At all 2,000 retail anchors the x87
control word is `0x007f` and MXCSR is `0x00001fa0`. The path-free sealed summary
and raw trace hashes are in
[`evidence/retail-reference-002677-2000-v1.json`](../evidence/retail-reference-002677-2000-v1.json).
The enhanced result is sealed in
[`evidence/retail-reference-002677-2000-enclosing-v1.json`](../evidence/retail-reference-002677-2000-enclosing-v1.json).
The 46-field shooting result is sealed in
[`evidence/retail-reference-002677-2000-shooting-v1.json`](../evidence/retail-reference-002677-2000-shooting-v1.json).
The 50-field Player-bullet lifecycle result is sealed in
[`evidence/retail-reference-002677-2000-player-bullet-lifecycle-v1.json`](../evidence/retail-reference-002677-2000-player-bullet-lifecycle-v1.json).
Its only semantic-projection exclusion is 3,898 collided-bullet
`sprite.pos.z` values: the retail draw callback writes 0.4 after the post-calc
anchor, while `UpdatePlayerBullets` overwrites all three sprite coordinates
from gameplay position before bounds or ANM reads them. Fired sprites are
14-by-14 and collided sprites are 16-by-16 in the observed profile.

Two interventions are explicit parts of the diagnostic environment. First,
Wine's `timeGetTime` reflects long host uptime while the game's last-frame
global begins at zero, so the probe sets that global to the already-read
current time and clears the local delta before gameplay. Second, XTest does not
reach Wine DirectInput on this host, so `Controller::GetInput` is changed to
return zero. ReplayManager subsequently replaces the complete replay input
mask at its authentic calc priority; the exported per-frame masks match the
reference. The probe verifies all three patched/anchored code byte sequences
before acting.

This closes neither whole-state equivalence nor the M0 milestone. The retail
probe currently exports a deliberately small root projection, not the eleven
canonical subsystem payloads; it covers one replay prefix, not the route
matrix; and finite agreement cannot prove noninterference, source/binary
correspondence, or guest refinement. Its immediate value is that the core
replay/RNG/player/global path now has a real retail oracle and a first-mismatch
mechanism.

## First sliced transition

The player-position slice consumes the now-retail-anchored input, player/time
gate, effective-rate bits, movement bounds, bomb multipliers, and four speed
records. It reproduces the source and mapped-instruction ordering without using
host floating point. Instead, normal finite binary32 inputs are decoded as
integer dyadics; each multiply and add is rounded explicitly to 24 significand
bits with ties to even before the next operation. Ordered clamps operate on the
same raw domain. Non-finite/subnormal values, subnormal results, overflow,
unsupported exponent gaps, and dead/spawning frames fail closed.

The 2,000 retail frames provide 1,999 consecutive transitions because the
first post-calc row has no retail-exported predecessor. All 1,999 expected x/y
bit pairs match. The vector and path-free manifest are in
[`evidence/player-motion-002677-2000-v1.bin`](../evidence/player-motion-002677-2000-v1.bin)
and its adjacent JSON file. This validates one reached trace and makes the
kernel concrete enough for proof and zkVM cost work; it does not prove the
integer arithmetic, PC24 control history, instruction/source binding,
projection noninterference, or unreachable-domain invariants.

## First OpenVM proof gate

The backend statement is deliberately narrower than a replay claim. The guest
reads the initial x/y words followed by 1,999 private input/environment records,
chains the shared Rust transition, and reveals exactly

```text
SHA256("zkTH06/openvm/player-motion/v1\0" || input_payload ||
       final_x_bits_le || final_y_bits_le).
```

The host builder independently obtains statement digest
`21e195a5...988f84e6`; pure execution, every metered run, and direct SDK decoding
of the generated proof expose those same 32 bytes for the full workload. This
design replaced an initial reconnaissance adapter that revealed only
start/end/count: that statement admitted an uncommitted existential transcript.
Full SHA-256 binding increases the 1,999-step meter result from 230,560,805 to
254,156,116 cells, a 10.2339% cost accepted to preserve the statement boundary.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 3,595 | 152,867 |
| 10 | 24,836 | 1,031,394 |
| 100 | 251,352 | 10,366,661 |
| 1,000 | 3,157,630 | 129,282,130 |
| 1,999 | 6,205,625 | 254,156,116 |

On the recorded 192-logical-CPU AMD EPYC 9654 host, `cargo openvm prove app`
completed in 75.65 seconds with 50,308,612 KiB peak RSS. Exact executable-
commitment verification completed in 0.12 seconds with 49,092 KiB peak RSS; a
one-bit-wrong expected commitment was rejected. The 872,364-byte proof and its
241,614-byte verifying key are tracked, and this command verifies them without
retail data or proving hardware:

```sh
cargo openvm verify app \
  --manifest-path zkvm/player-motion-openvm/Cargo.toml \
  --proof evidence/openvm-player-motion-1999-v1.app.proof \
  --app-vk evidence/openvm-player-motion-v1.app.vk \
  --app-commit evidence/openvm-player-motion-v1.app-commit.json
cargo +1.91.1 run --release --locked \
  --manifest-path tools/openvm-proof-inspect/Cargo.toml -- \
  evidence/openvm-player-motion-1999-v1.app.proof \
  21e195a5a5a123c01d9f48c876949340f6922e55215ced83d74dd06a988f84e6
```

This closes real-backend execution, proof generation, exact guest commitment,
and a fixed workload/result commitment for the first slice. It does not derive
the eleven movement-environment words from prior TH06 state; until the enclosing
transition does so, a prover can commit a different internally valid workload.
It also establishes no whole-game equivalence, formal arithmetic theorem, or
zero-knowledge/privacy result. Those limits are recorded in
[`evidence/openvm-player-motion-1999-v1.json`](../evidence/openvm-player-motion-1999-v1.json).

## Enclosing player-state proof gate

The next adapter removes the earlier proof's principal witness-trust problem.
Its `ZKPSI1` private payload contains one fixed character/shot configuration
and 1,999 little-endian replay input masks. It contains no initial position,
life state, timer, time-stop flag, rate, movement bounds, bomb multipliers, or
character speeds. The guest constructs the fixed first post-calc anchor and
iterates the shared enclosing transition, revealing

```text
SHA256("zkTH06/openvm/player-state/v1\0" || input_payload ||
       final_game_frame_le || final_x_bits_le || final_y_bits_le ||
       final_life_state || final_flags || 0x0000 || final_timer_le).
```

The enhanced Wine/reference gate compares 40 fields on all 2,000 frames. The
compact `ZKPSV1` evidence vector independently checks all 1,999 full-state
transitions, including the invulnerable-to-alive transition at frame 240. A
static artifact binds the selected contract to 55 retail instruction roles,
five mapped functions, 30 pinned source anchors, and the earlier fixed
position/speed/bounds audit.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 3,688 | 153,761 |
| 10 | 21,369 | 828,793 |
| 100 | 212,261 | 8,170,122 |
| 1,000 | 2,761,414 | 107,139,819 |
| 1,999 | 5,412,644 | 209,865,030 |

The full private payload falls from 95,976 to 4,018 bytes (95.8135%), while
metered cells fall by 44,291,086 (17.4267%) despite the stronger state/result
statement. Application proving took 73.18 seconds and peaked at 49,431,532 KiB
RSS; exact verification took 0.11 seconds. The expected executable commitment
and statement digest both pass, while one-bit changes to each are rejected.
The tracked bundle is
[`evidence/openvm-player-state-1999-v1.json`](../evidence/openvm-player-state-1999-v1.json).

This closes per-frame environment witnesses only for the named profile. The
post-calc frame-one anchor is still fixed rather than derived from
registration/pre-stage scheduling. Bomb input or an active bomb fails closed;
collision death, spawning/respawn, ECL time-stop writers, and non-full-speed
timer arithmetic are not implemented. The 55-instruction artifact is exact
static signature evidence, not a verified decoder, compiler-correctness proof,
whole-program writer theorem, or Rust refinement theorem.

## Player shooting-cadence proof gate

The next refinement follows `Player::OnUpdate` through
`HandlePlayerInputs`, `StartFireBulletTimer`, and
`UpdateFireBulletsTimer`. It derives `isFocus`, `previousFrameInput`, and the
fire timer from the preceding Player state and current replay mask. The
same-frame ordering is explicit: a shoot press starts timer 0, the active
timer emits at most one `SpawnBullets(player, timer)` request, then the
full-speed tick advances it; post-tick value 30 resets to `(-999, -1)`.

The selected 2,000-frame interval has no dialogue, bomb, hit, or time-stop
writer. The reference and retail executable match on all 46 observed fields.
The `ZKSHV1` vector checks every one of the 1,999 consecutive transitions and
derives 1,590 callback requests. A separate sealed audit binds 54 retail
instruction roles across eight mapped functions and 33 pinned source anchors,
including the focus selector and both fixed character callback dispatches.

The `ZKSHI1` OpenVM input remains 4,018 bytes: only configuration plus one
`u16` replay mask per transition. The public digest additionally commits final
focus, previous input, fire timer, and cumulative callback count.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 4,250 | 173,404 |
| 10 | 21,948 | 848,771 |
| 100 | 215,342 | 8,273,675 |
| 1,000 | 2,792,207 | 108,171,997 |
| 1,999 | 5,468,598 | 211,737,944 |

The added state/callback schedule costs 1,872,914 cells (0.8924%) over the
enclosing-state proof without enlarging the private payload. Application
proving took 75.57 seconds and 49,103,488 KiB peak RSS; exact commitment
verification and public-digest inspection pass, while one-bit-wrong variants
are rejected. The tracked bundle is
[`evidence/openvm-player-shooting-1999-v1.json`](../evidence/openvm-player-shooting-1999-v1.json).

This layer stops at the `SpawnBullets` call boundary. Bullet-slot reuse,
character/shot callback geometry, power-dependent patterns, and existing
bullet update/collision effects remain outside the transition. The static
audit also leaves source/compiler correspondence, complete writer
noninterference, and Rust refinement as explicit obligations.

## Local Player bullet-spawn proof gate

The next refinement enters the Reimu-A callback and returns at the
`SpawnBullets` call boundary. The retail probe is pinned to entry `0x00429820`
and its unique caller return `0x0042978b`. The matching reference scope records
complete pre/post arrays for 80 slots, four non-laser dormant carry fields,
active geometry and timers, player/orb positions, and the requested/first-tick
ANM projection. Across the same 2,000-frame prefix, all 1,590 calls match and
422 bullets are initialized. Pre-call occupancy reaches 24 of 80 slots, so no
observed callback is capacity-truncated.

The `ZKPBV1` vector binds this finite oracle and a 56-instruction static audit.
The Rust transition fails closed outside Reimu A power 0--31 and timer 0--29,
scans the lowest unused slot exactly, preserves all callback-unwritten fields,
and emits raw geometry. Position addition uses the integer PC24 model. The
five velocity pairs are fixed raw outputs bound to the pinned table/trace;
host trigonometry is not used and helper equivalence remains open.

The fourth OpenVM guest receives each complete pre-call slot-state array,
derives the allocations, and hashes every initialized bullet into its public
statement. The full 1,590-call workload has a 197,180-byte private payload and
public digest
`bcb4548e9ab8772a1c4a2b05ef4b667995dbd98ac47d233cc6c889512e60283d`.

| Spawn calls | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 8,918 | 378,104 |
| 10 | 47,560 | 2,010,154 |
| 100 | 449,480 | 18,882,447 |
| 1,000 | 4,480,565 | 188,128,190 |
| 1,590 | 7,394,181 | 309,751,316 |

Application proving took 98.60 seconds and peaked at 51,626,064 KiB RSS;
verification took 0.12 seconds. Exact commitment/public-digest checks pass and
one-bit-wrong variants fail. The tracked bundle is
[`evidence/openvm-player-bullets-1590-v1.json`](../evidence/openvm-player-bullets-1590-v1.json).

This is a batch of local transitions, not an enclosing bullet subsystem. Each
pre-state is independently observed. `UpdatePlayerBullets`, collision, ANM
termination, and slot reclamation must next derive one call's reachable
pre-state from preceding Player/bullet state. The proof also does not discharge
compiler correspondence, trig-helper semantics, complete writer
noninterference, ranks 4--5, or other character/shot routes.

## Linked Player bullet-lifecycle proof gate

The enclosing refinement removes the local proof's independently observed
slot-state inputs for the prefix where every liveness writer is owner-local.
The fixed post-calc frame-1 anchor contains an empty 80-slot pool and zero
dormant carry. Each step first derives Player motion and shooting state, then
updates every fired type-0 bullet with the mapped PC24 multiply/add order,
copies gameplay position to sprite position, applies the 14-by-14 bounds test,
ticks the fixed nonterminating script-1088 ANM and age timers, and finally
performs rank-1 allocation in the lowest free slots.

The complete 2,000-frame oracle identifies the exact stopping rule.
EnemyManager first changes a fired Player bullet to collided at game frame 208;
the linked profile therefore includes frames 1--207 and rejects another step.
EnemyManager writes `positionOfLastEnemyHit` on 70 earlier frames, but the
selected type-0 route does not read the target: only the excluded type-1 homing
route does. The static artifact inventories all five lexical `bulletState`
writers and checks 29 instruction roles across eight mapped functions, while
leaving alias completeness, ANM-data correspondence, and compiler/refinement
proofs explicit.

The `ZKPLV1` vector checks the derived state exactly at all 207 anchors. Its 206
transitions contain 173 spawn calls, 35 bullet initializations, 30 bounds
reclamations, at most seven live slots, and five final live slots. Unlike the
197,180-byte local-callback proof input, the `ZKPLI1` private payload is only
436 bytes: a fixed header followed by 206 replay masks. The public statement
hashes every intermediate Player/bullet state, not merely the endpoint.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 40,273 | 1,575,949 |
| 10 | 344,217 | 13,306,422 |
| 100 | 5,380,025 | 209,163,788 |
| 206 | 12,192,123 | 474,516,189 |

Application proving took 118.01 seconds, 4,279.43 user CPU seconds, and
50,859,740 KiB peak RSS without swapping. Verification took 0.18 seconds and
50,116 KiB peak RSS. Exact executable-commitment and decoded public-digest
checks pass; one-bit-wrong commitment and digest checks fail. The tracked
bundle is
[`evidence/openvm-player-bullet-lifecycle-206-v1.json`](../evidence/openvm-player-bullet-lifecycle-206-v1.json).

This is the first persistent bullet-state proof, but only for the finite
collision-free Reimu-A rank-1 prefix. It does not yet derive the frame-208
Enemy/ECL collision, bind script 1088 directly to ANM data, prove complete
writer noninterference or compiler correspondence, or cover homing, other
routes/ranks, bombs, death, power, items, or whole-game state.

## Enclosing early-Enemy collision proof gate

The next transition composes the former stopping writer instead of weakening
the boundary. Starting from the same empty frame-1 anchor, it derives Stage-1
timeline spawns at frames 129, 145, 161, 177, and 193; moves each fixed `Sub0`
enemy in manager order; carries the in-bounds bit; advances ECL time, angle,
angular velocity, and axis speed; and executes Player-bullet AABB damage before
life, target, death, and score updates. The 207 transitions reach frame 208,
where slot 2 deals 48 damage to the first eight-life enemy, enters the collided
animation, removes Enemy slot 0, updates the target, and raises score to 390.

New address-bound instrumentation records every `Player::CalcDamageToEnemy`
entry/return with the complete 80-slot pool and a raw Enemy/ECL projection. In
225 frames the retail and reference traces match exactly: 249 calls, four
damaging calls, first damage at frame 208, at most five enemies, and no trace
overflow. The proof prefix selects 200 calls and the unique first hit. A sealed
static audit maps 25 instruction roles across eight retail functions and binds
the Stage-1 ECL data. The compact `ZKEGP1` vector checks all 207 transitions
against the Rust state without supplying Enemy state as witness.

The `ZKEGI1` OpenVM payload is a 24-byte fixed header plus 207 replay masks, or
438 bytes total. The public digest commits every retained Enemy projection and
the final collision metrics.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 66,121 | 2,598,121 |
| 10 | 607,280 | 23,638,475 |
| 100 | 7,057,753 | 274,253,314 |
| 207 | 19,787,280 | 769,444,525 |

Application proving took 203.58 seconds, 6,473.21 user CPU seconds, and
52,632,376 KiB peak RSS without swapping. The 2,513,550-byte proof verifies in
0.22 seconds with 53,520 KiB peak RSS. SDK deserialization yields public digest
`0909a289f39eb51f601649161ff98ca479a114dbc9b449a0939202c8b3f73f40`;
one-bit-wrong executable and public commitments are rejected. The tracked
bundle is
[`evidence/openvm-early-gameplay-207-v1.json`](../evidence/openvm-early-gameplay-207-v1.json).

This remains a finite Reimu-A rank-1 prefix, not a universal equivalence
theorem. The 40-entry curve table is program data indexed only by derived ECL
time and agrees with both oracles, but still needs refinement to the pinned x87
`fsincos` behavior. Sub0 shooting effects are omitted from this projection and
need a noninterference proof; the post-death time-81 update is omitted only
after collision position and removal are derived. RNG, enemy bullets, items,
bombs, Player death/respawn, dialogue, other routes, and later ECL paths remain
outside the kernel.

## Complete first-wave proof gate

The next enclosing state replaces the single `collided_slot` marker with the
complete 80-entry bullet-state map and carries collided bullets through their
slowed movement and collision-script timers. Starting from the frame-208 state
derived by the preceding kernel, it executes another 21 transitions and
derives the remaining deaths at frames 213, 219, 224, and 229. Collision slots
are 2, 3, 4, 0, and 1; every hit deals 48 damage and contributes 90 hit score
plus 300 death score. The frame-229 endpoint therefore has score 1950, five
collided bullets, six active bullets, and no remaining first-wave Enemy.

The enlarged address-bound Wine trace and independent Linux reference match
for 260 frames over the full Enemy/collision profile. The proof vector commits
all active-bullet fields (104 bytes per active record), every retained Enemy,
target, and score field. It contains 253 damage calls and observes RNG
generation 157, but RNG/effects are not accepted as witnesses or retained by
the guest.

The `ZKFWI1` OpenVM payload is 480 bytes: a fixed 24-byte header plus 228 replay
masks. Its public digest is
`1825b64b0a3ac10d26ecd9d82052ab58c68bb5250d89dba85fea79f727f562a8`.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 82,305 | 3,219,079 |
| 10 | 758,445 | 29,483,552 |
| 100 | 9,468,443 | 368,988,475 |
| 207 | 25,262,242 | 985,032,840 |
| 228 | 28,276,048 | 1,104,665,874 |

Application proving took 299.07 seconds and 51,442,624 KiB peak RSS without
swapping; verification took 0.28 seconds. Exact executable/public commitments
pass and one-bit variants fail. The tracked bundle is
[`evidence/openvm-first-wave-228-v1.json`](../evidence/openvm-first-wave-228-v1.json).

This boundary is intentionally frame 229, not an arbitrary proof-size cutoff.
Enemy deaths spawn omitted Item state; the first observed feedback into the
retained projection is a small-power collection that adds 10 score (and power)
at frame 249. Extending beyond frame 229 therefore requires composing Item
spawn/motion/collision rather than claiming it noninterfering. Direct collision
ANM decoding, alias-complete RNG/effect and Sub0-shooting noninterference, x87
`fsincos` refinement, and source/binary/guest correspondence remain open.

## First Item-feedback proof gate

The next enclosing state now composes the stopping Item writer instead of
extending the earlier omission claim. Enemy deaths advance a derived
random-drop cursor; the third death at frame 219 selects the first random-table
entry and allocates one small-power Item in slot 0. Its initial vertical
velocity is raw binary32 `0xc00ccccd` (-2.2), then the transition applies raw
binary32 acceleration `0x3cf5c28f` (+0.03 per frame), advances the Item timer,
and evaluates the retail-ordered Player/Item AABB comparisons.

The Item remains active from frames 219 through 248. Collection at frame 249
changes score 1950 to 1960, power 0 to 1, and subrank 0 to 1. The manager's
`itemCount` is intentionally still 1 in that post-frame snapshot because the
active count is accumulated before collection; it becomes zero on the next
manager pass. The transition also derives collided-bullet ANM slot reclamation
at frames 238, 243, and 249. The endpoint has two collided bullets, three
active bullets, no live Enemy, and no active Item.

The address-bound Wine trace and independent Linux reference agree for 300
frames over the added Item records, allocator/random cursors, power, subrank,
and all preceding fields. The `ZKFIV1` vector retains every active Item field
and checks all 248 linked transitions from the same fixed frame-1 anchor. The
`ZKFII1` OpenVM payload is 520 bytes: a fixed 24-byte header plus 248 replay
masks. No Item, cursor, collision, power, subrank, score, bullet, or Enemy value
is witness-supplied. Its public digest is
`552ea02d7946a1da7c2cc1d7d0a9600ea21156cb2a1aa4842ef7623d6dd19cc6`.

| Transitions | Guest instructions | Metered cells |
| ---: | ---: | ---: |
| 1 | 76,117 | 2,973,497 |
| 10 | 690,887 | 26,852,082 |
| 100 | 8,787,114 | 342,469,754 |
| 207 | 23,918,663 | 932,639,163 |
| 228 | 27,136,950 | 1,060,183,752 |
| 248 | 29,288,817 | 1,146,265,201 |

Application proving took 290.44 seconds and 52,115,224 KiB peak RSS without
swapping; the 3,472,435-byte proof verifies in 0.29 seconds. Exact executable
and public commitments pass, while one-bit variants fail. The tracked bundle
is [`evidence/openvm-first-item-248-v1.json`](../evidence/openvm-first-item-248-v1.json).

This closes the first concrete omitted-state feedback counterexample. It is
still finite differential/static evidence rather than a universal refinement
proof. The new fail-closed boundary is frame 249: before proceeding, the
second Enemy wave must bring its ECL context, RNG effects, and Enemy bullets
into the canonical transition. Item/collision ANM decoding, alias-complete
effect and Sub0-shooting noninterference, x87 refinement, and code
correspondence remain open; Lean is deliberately not on this critical path.

## Local corpus result

The downloaded corpus is excluded from Git. Provenance and input hashes are in
[`replays/README.md`](../replays/README.md).

| Replay | Difficulty / shot | Logic ticks | Final stage frame | Computed final score | Terminal |
| --- | --- | ---: | ---: | ---: | --- |
| `th6_ud000134.rpy` | Lunatic / Marisa B | 84,817 | 16,485 | 181,778,020 | `replay-complete` |
| `th6_ud000232.rpy` | Lunatic / Reimu B | 86,676 | 16,727 | 136,978,560 | `replay-complete` |
| `th6_ud002677.rpy` | Normal / Reimu A, no-miss no-bomb | 85,759 | 17,283 | 172,519,700 | `replay-complete` |
| `th6_udLuRB.rpy` | Lunatic / Reimu B | 118,605 | 26,233 | 804,515,970 | `replay-complete` |

The Stage 6 end score is computed by gameplay; playback restores the preceding
stage's score but does not restore the current stage block's end score. Exact
final-score agreement is therefore useful self-consistency evidence. It still
does not establish equivalence with the shipped executable.

Two independent 1,000-tick runs of the Normal replay produced byte-identical
JSONL with SHA-256:

```text
d4606beb09ea9040b0e747d95b2dc7ebe70d36f5b5c152c8289b6074e69e899a
```

All four full runs completed in 1.1–1.6 seconds each on the initial host and
used less than 40 MiB RSS without tracing. These are local measurements, not a
performance guarantee.

Two independent complete canonical-trace runs of `th6_ud002677.rpy` produced
85,759 byte-identical records and SHA-256:

```text
ea0cdf948ba7668cba31064dfa421a9c279fdab28bdbd1d57c817ba13db84117
```

Each run wrote a 50,769,392-byte digest trace and hashed 6,192,210,130 bytes of
selected payload. Concurrent local runs completed in 31.90 and 32.04 seconds
with less than 39 MiB RSS. The first attempt to include all named ANM members
was nondeterministic at Stage record zero because disabled interpolation fields
were uninitialized; guarded future-live encoding restored determinism. This is
a useful projection-design counterexample, not original-game equivalence.

## Arithmetic census result

The verified v1.02h executable contains 10,100 x87 instruction lines in a
complete linear `.text` disassembly. The upstream mapping attributes 5,980 to
159 implemented `th06::` functions, including 26 direct `fsincos` sites, 10
`frndint` sites, and 1,793 stores. Of those stores, 1,713 target DWORDs and 80
target QWORDs. A further 163 direct game-to-helper call sites reach 18 x87
helpers or wrappers, led by 77 `__ftol2`, 16 `sin`, 16 `cos`, 11 `sqrt`, and 7
`atan2` calls.

The mapped game surface also contains 244 `fcomp` sites: 236 have DWORD and
eight have QWORD memory operands. Every one has a complete immediate
`fnstsw ax`/mask/conditional-branch consumer, spanning eleven signatures. At
all 77 `__ftol2` sites a straight-line scan observes EAX (or AL) and never EDX;
the preceding x87 operations are also inventoried. A subsequent bit-mask scan
refines this to 75 full-EAX and two AL-only observations. Because 42 stopping
points still have live EDX bits, this remains bounded syntactic evidence rather
than complete data-flow proof.

The CRT trigonometric wrappers embed x87 control word `0x027f` (53-bit
significand precision, round-to-nearest-even, exceptions masked). The retail
anchor instead observes `0x007f` (24-bit precision) at every sampled post-calc
boundary. This establishes a boundary observation, not the word at every
instruction: wrappers may change and restore precision internally. Entry,
per-site control flow, and transient profiles must still be measured and
constrained explicitly. The complete audit and soundness consequences are in
[`arithmetic-audit.md`](arithmetic-audit.md).

The arithmetic oracle now compares `add`, `sub`, `mul`, `div`, `sqrt`,
binary32/binary64 `fstp`, `frndint`, and signed 32/64-bit `fistp` results plus
all six x87 exception bits. On an AMD EPYC 9654, 30,002,582 deterministic
result/exception tuples across binary32-derived and PC53 extended inputs,
nearest-even, and toward-zero produced no mismatch. The experiment itself
found and rejected a naive denormal-operand rule before the instruction-specific
model passed. An additional 4,000,220 DWORD/QWORD comparison tuples matched,
including fixed ordered/unordered and exception-priority cases. Separately,
1,000,014 executions of the exact extracted `__ftol2` body matched signed-i64
dyadic truncation and returned an empty x87 stack. A focused second campaign
matched 1,000,154 ECL sentinel classifications, including 3,084 recognized
variable operands and nine invalid exceptional cases, for 2,000,168 exact
helper executions in total. These remain host-specific counterexample searches:
load exceptions, universal exceptional helper semantics, transcendentals,
verified address decoding, reachability, and model-to-code proof remain open.
The reproduction and claim boundary are in
[`../arithmetic/README.md`](../arithmetic/README.md).
The corresponding 321 original addresses are now frozen in
[`../arithmetic/obligations-v1.json`](../arithmetic/obligations-v1.json), with
every slice disposition and every conversion range explicitly unproved; the
discharge protocol is in
[`arithmetic-obligations.md`](arithmetic-obligations.md).
The derived source ledger classifies 68 calls as omission candidates and nine
as retain candidates, but leaves every proof status open. The retained ECL call
observes only membership in `-10025..-10001`; the other eight retained calls
are point-item scoring conversions with a total exceptional-input quotient.

The score blocks load the same binary32 `Item.currentPosition.y` field twice,
compare signed EAX with 128, and apply difficulty constants before adding the
result to gameplay score. A Lean rational model derives `-4..452` for finite
items from ordered collection overlap and the expected player bounds, then
proves scores remain in `27600..300000`. Its total coordinate model treats
infinities as separated and NaN as a possible collision whose masked-invalid
helper result has low EAX zero. Thus sound score bounds need a finite bounded
player box, but no longer a universal item-position finiteness invariant.

A 95-instruction retail audit now traces the player center from initial and
respawn value 384 through movement, the ordered `16..432` clamp, and construction
of the radius-12 grab box. Its total Lean model proves that both infinities are
clamped into range and only NaN survives. This materially narrows the remaining
invariant to non-NaN movement candidates plus complete writers, initialization,
update scheduling, exact binary32/x87 behavior, verified correspondence, and
guest refinement. It does not assume the adaptive effective frame multiplier
is fixed at one.

The ECL resolver exposes player-y as a readonly variable, but its increment and
decrement handlers bypass that guard. An independent walk of the seven fixed
retail ECL files finds 1,844 candidate outputs and 80 such unchecked writes;
none names player x, y, or z, and the unchecked destination support contains
only four local-variable IDs. This removes a concrete fixed-data alias threat
once the still-open archive extraction, runtime parser/dispatch, immutability,
and code bindings are proved; it is not whole-program writer completeness. A
GDB debug-runner probe observed 2,081 finite collections in the four-replay
corpus, with no sample outside the candidate interval. This remains invariant-
discovery evidence, not retail-binary evidence or a proof.
The remaining control invariants are difficulty in `0..4` and pre-item score in
`0..999999999`; the latter condition is sufficient in Lean to rule out u32
wrap for one bounded award.

## Remaining M0 gates

1. Close or explicitly constrain the selected projection. Inactive Effect
   residue and dynamic ScreenEffect jobs are known open noninterference cases;
   see [`state-projection-audit.md`](state-projection-audit.md).
2. Compose the second Enemy wave together with its RNG/ECL and Enemy-bullet
   state. The preceding death-Item feedback is now closed through frame 249.
3. Add a field-level canonical snapshot at a selected tick so a subsystem
   mismatch can be reduced to its first field.
4. Export the same schema from the original executable or an exact-reference
   build and identify the first differing field.
5. Record the entry x87/CPU profile, instrument reached arithmetic sites,
   cover load/remainder and exceptional helper behavior where reachable, prove
   ECL helper-to-classifier refinement and discharge the point-item player
   candidate/writer/scheduling plus total collision/helper quotient (including
   the fixed-ECL extraction/parser/handler binding),
   and replace host-libm behavior with an exact, address-bound arithmetic
   baseline; prove skipped-draw arithmetic noninterference before removing it.
6. Add canonical-proof playback that derives stage transitions and rejects a
   replay whose stage snapshots do not match live state.

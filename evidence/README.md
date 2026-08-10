# Differential evidence

This directory keeps compact, proprietary-byte-free summaries of local
experiments whose full traces cannot be reproduced in public CI without a
legally supplied TH06 v1.02h installation.  Each summary pins the executable,
replay, trace hashes, tool environment, observed projection, and explicit
claim boundary.

`retail-reference-002677-2000-v1.json` is the first shipped-executable anchor.
It compares 2,000 post-calc frames from the Wine-run retail executable with the
Linux reference runner.  The compared 34-field projection matches on every
frame, including the complete environment consumed by the player-position
slice.  This is finite differential evidence, not whole-state equivalence and
not a formal proof.

`retail-reference-002677-2000-enclosing-v1.json` extends the same 2,000-frame
comparison to 40 fields.  The six additions are the configured framerate
multiplier, respawn timer, active-bomb flag, and the previous/subframe/current
words of the invulnerability timer.  Every field matches; the same finite-
projection and one-replay limitations apply.

`player-motion-002677-2000-v1.bin` and its JSON manifest retain 1,999
consecutive position transitions derived from that matched retail trace.  The
fixed-width vector contains numeric inputs, environment fields, and expected
raw binary32 positions only; it contains no executable, DAT, or replay bytes.
It is a regression oracle for the narrow player-position kernel, not an
independent proof of its arithmetic or source correspondence.

`openvm-player-motion-1999-v1.json` records the first real backend milestone.
The adjacent OpenVM v2.0.1 application proof, verifying key, executable, and
expected executable-commitment descriptor are tracked so verification needs
neither retail data nor proving hardware.  The guest executes all 1,999
transitions and publishes
`SHA256(domain || private workload || computed final x/y)`; direct SDK decoding
confirmed that the proof's 32 authenticated public bytes equal the independently
computed statement digest.  The manifest binds every artifact and guest source
by SHA-256 and records meter/prove/verify results.  This proves the exact sliced
program and hash-bound workload/result, not derivation of its eleven environment
words from a complete TH06 state.  The optional pinned SDK utility under
`tools/openvm-proof-inspect/` makes the public-value comparison reproducible;
it complements rather than replaces cryptographic proof verification.

`player-state-002677-2000-v1.bin` and its JSON manifest are the stronger
enclosing-state oracle.  The `ZKPSV1` records retain only frame index, replay
input, reached life state/flags/timer, and expected position; rate, bounds,
multipliers, and speed records are validated as fixed profile facts rather than
fed to the kernel.  The 1,999 transitions include the frame-240 change from
invulnerable to alive.

`openvm-player-state-1999-v1.json` records the corresponding OpenVM proof.  Its
4,018-byte private payload contains a fixed character/shot header and one
`u16` replay mask per transition, versus 95,976 bytes in the earlier
environment-witness proof.  The guest derives the anchor, life-state/timer
sequence, time-stop carry, speed table, bounds, rate, and inactive-bomb
multipliers, then authenticates the payload and complete final player state.
The tracked proof verifies at the recorded executable commitment; independent
inspection matches statement digest
`1743dee39bbb8ec0aea47858837da4c8025929d5e31eabaa7be07fd0accff7fd`,
and one-bit-wrong commitment and digest tests fail.  This closes environment
witnesses only for the named full-speed/no-bomb/no-hit/no-time-stop-write
profile.  The fixed post-calc anchor, collision/death/respawn, bombs, external
time-stop writers, and non-full-speed timers remain outside the claim.

`retail-reference-002677-2000-shooting-v1.json` raises the same retail oracle to
46 fields.  The additional six fields are the GUI current-message predicate,
Player focus flag and previous input mask, and the previous/subframe/current
words of the fire timer.  All 2,000 frames match, and the dialogue predicate is
false throughout the selected interval.

`player-shooting-002677-2000-v1.bin` (`ZKSHV1`) binds those observations to the
static shooting audit and reconstructs the effect at each transition.  Its
1,999 transitions contain 1,590 derived `SpawnBullets(player, timer)` requests,
including the same-frame timer-0 request and the reset/restart cadence.  It
stops at that call boundary and contains no bullet-slot or shot-geometry claim.

`openvm-player-shooting-1999-v1.json` records the third OpenVM proof.  The guest
derives focus, `previousFrameInput`, fire-timer state, and cumulative callback
count without enlarging the 4,018-byte replay-input payload.  It executes
5,468,598 instructions and meters 211,737,944 cells.  The tracked proof's
authenticated public digest is
`a6008bb749de4fccd4d120d11f710d3c41f4c9ee17a53d419ebc1a2470c82060`;
the exact executable commitment verifies and one-bit-wrong commitment/digest
checks fail.  Static instruction/source alignment, finite differential
agreement, and the zk proof remain separate evidence layers: compiler
correspondence, complete writer noninterference, and callback geometry are open.

`retail-reference-002677-2000-player-bullets-v1.json` adds one structured field
to form a 47-field profile. At each of 1,590 callback entries it compares the
address-bound retail and instrumented-reference pre/post projection: all 80
slot states, all four dormant carry fields, active geometry/timers, player and
orb positions, and the requested/first-tick ANM projection. The selected run
initializes 422 bullets, reaches at most 24 active slots before a call, and
never truncates a pattern for lack of capacity.

`player-bullets-002677-2000-v1.bin` (`ZKPBV1`) converts those calls into a
fixed-width, proprietary-byte-free local-transition vector. It covers Reimu A
power 0--31 (ranks 1--3), retains every independently observed pre-slot state,
and records up to four expected allocations per call. The transition uses raw
table-bound trigonometric results and integer PC24 position addition; it does
not substitute host `libm`.

`openvm-player-bullets-1590-v1.json` records the fourth OpenVM application
proof. The 197,180-byte private payload contains 1,590 callback records; the
guest derives and hashes all 422 initialized bullets. It executes 7,394,181
instructions and meters 309,751,316 cells. The proof verifies against the exact
executable commitment, its decoded public digest is
`bcb4548e9ab8772a1c4a2b05ef4b667995dbd98ac47d233cc6c889512e60283d`,
and one-bit-wrong commitment/digest checks fail. Because the input pre-states
are independently observed rather than derived through bullet update,
collision, and ANM reclamation, this is not an enclosing cross-frame proof.

`source/openvm-player-motion-v1/player-motion-lib.rs` preserves the exact
library source compiled into the earlier immutable proof.  The live crate later
gained the enclosing-state module, so retaining the old source by hash keeps
both proof bundles independently auditable without pretending the old vm
executable was built from the new file.

`source/openvm-player-shooting-v1/zkvm-Cargo.toml` similarly preserves the
workspace manifest bound by the shooting proof. The live workspace later added
the Player-bullets crate; that member-list change does not rewrite the older
proof's claimed source input.

The raw retail/reference JSONL files, debugger logs, executable, DAT archives,
and generated Wine directory stay under ignored local storage.

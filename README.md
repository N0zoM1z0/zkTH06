# zkTH06

Replay-verified Touhou 6 gameplay semantics for zero-knowledge execution.

The goal is to prove that a private frame-input stream advances a committed
Touhou Koumakyou v1.02h gameplay state machine from a canonical initial state to
an accepted result. Before freezing a zkVM guest, the project must first make
that state machine agree frame-for-frame with the shipped 32-bit Windows game.

> **Evidence boundary:** an address-bound Wine probe now matches the shipped
> executable and Linux reference for a 50-field semantic gameplay projection over
> the first 2,000 frames of one tracked replay. An enlarged raw-bit projection
> now also matches Enemy/ECL, Item, RNG, Player-collision, and active Enemy-bullet
> state over 1,200 frames, crossing the first seven Enemy bullets at frame 1180.
> Three presentation-only fields are excluded with explicit next-read arguments:
> collided-bullet sprite z, Item offscreen-indicator state, and ANM sprite load
> handles. This is finite differential evidence, not whole-state equivalence.
> The current runner remains an instrumented reference harness, not final proof
> semantics.

The first proof-oriented executable slice is now present under `zkvm/`: an
integer-only implementation of the PC24 player-position update whose inputs and
outputs remain raw binary32 bits. It matches 1,999 consecutive transitions
derived from the retail anchor. The current enclosing transition no longer
accepts its eleven movement-environment words per frame: from one fixed
character/shot configuration and the preceding state it derives life state,
time-stop carry, invulnerability timer, character speeds, movement bounds,
full-speed rate, and inactive-bomb multipliers. An OpenVM v2.0.1 RV32IM guest
executes that transition and publishes a full SHA-256 commitment to its private
input masks and computed endpoint. Its tracked application proof verifies
against the exact guest commitment. This freezes a narrow, fail-closed
full-speed/no-bomb/no-hit profile, not a complete Player guest or a formal
refinement theorem.

The next Player refinement is also executable and proven through the shooting
cadence boundary. A separate integer-only crate derives focus,
`previousFrameInput`, fire-timer start/tick/reset behavior, and 1,590
`SpawnBullets(player, timer)` requests from the same anchor and replay masks.
All 1,999 transitions agree with the 46-field retail/reference oracle. Its
OpenVM proof keeps the private payload at 4,018 bytes and meters 211,737,944
cells. Bullet-slot allocation and the four character/shot callback geometries
are deliberately not part of that enclosing cadence claim.

The callback boundary is now refined one step further for Reimu A ranks 1--3.
An address-bound retail hook and matching reference instrumentation record all
80 pre/post slot states, dormant carry fields, active bullet geometry, and ANM
request projection at every callback. All 1,590 calls and 422 initialized
bullets match exactly. A local integer-only transition derives timer gates,
power rank, lowest-free-slot allocation, and raw geometry; a fourth OpenVM
application proof executes the complete batch and publicly commits every
initialized output. This is intentionally a collection of local function
transitions: within that local proof, independently observed pre-call states
are not linked by `UpdatePlayerBullets`, ANM reclamation, or Enemy collision.

The first persistent Player/bullet state boundary is now closed for a smaller
prefix. Starting from the fixed empty pool at gameplay frame 1, a fifth OpenVM
guest consumes only 206 replay masks and derives Player motion, shooting
cadence, rank-1 straight-bullet movement, 14-by-14 bounds reclamation, fixed
nonterminating ANM/timer effects, and allocation through frame 207. All 35
initializations and 30 reclamations agree with the 50-field retail/reference
oracle at every frame. The 436-byte private payload contains no per-frame slot
state. The synchronized proof costs 12,192,123 instructions and 474,516,189
metered cells.
It deliberately rejects frame 208, where EnemyManager first changes a fired
bullet to collided; Enemy/ECL composition is the next soundness boundary.

That boundary is now crossed by an enclosing early-gameplay kernel. A sixth
OpenVM guest consumes 207 replay masks and derives the first five Stage-1
`Sub0` timeline spawns, movement, ECL time and angle, in-bounds gating, 200
damage calls, the unique slot-2 bullet collision, first-enemy death, target
selection, and score 390 through frame 208. Retail Wine and the independently
built reference agree over a 225-frame raw Enemy/collision projection. The
438-byte private payload contains no Player, bullet, Enemy, ECL, collision,
life, target, or score witnesses. Its tracked proof costs 19,787,280
instructions and 769,444,525 metered cells. The curved-axis table is selected
only by derived ECL time, but proving it refines the pinned x87 `fsincos` path
and proving omitted Sub0 shooting effects noninterfering remain explicit
soundness obligations.

The enclosing successor now closes the entire first Stage-1 wave rather than
stopping after one hit. A seventh OpenVM guest derives persistent collided-
bullet motion and ANM timers plus the remaining four collisions and deaths at
frames 213, 219, 224, and 229. Its 480-byte private payload is still only a
fixed header and 228 replay masks; the public digest commits every active
Player-bullet and Enemy raw-bit projection at every frame. The final state has
score 1950, five collided bullets, six active bullets, and no live first-wave
Enemy. The proof costs 28,276,048 instructions and 1,104,665,874 metered cells.
Retail Wine and the independent reference match the enlarged projection over
260 frames. The seventh kernel stops at frame 229 because death-spawned Item state is
not yet retained and first feeds score/power at frame 249; this is the next
enforced subsystem boundary rather than an assumed noninterference claim.

The eighth enclosing kernel now closes that feedback boundary. It derives the
random-drop cadence across all five deaths, the frame-219 small-power Item
spawn, 30 frames of raw-bit movement, Player collection, collision-script slot
reclamation, and the frame-249 score/power/subrank writes. Retail Wine and the
independent reference match the enlarged Item projection for 300 frames. The
520-byte OpenVM payload still contains only a fixed header and 248 replay
masks; the endpoint has score 1960, power 1, subrank 1, two collided bullets,
three active bullets, and no active Item. The proof costs 29,288,817
instructions and 1,146,265,201 metered cells. It fails closed before the second
Enemy wave, whose RNG/ECL context and Enemy bullets are the next subsystem
boundary.

The ninth enclosing kernel crosses that boundary through frame 350. From the
same fixed frame-1 anchor and only 350 replay masks it derives the second
timeline group, six Enemy spawns, ECL timers and movement, five deaths, exact
death-effect RNG consumption, two random-drop Items, allocator cursors, and
score 3910. The Enemy-bullet manager and pool are retained explicitly and are
derived empty throughout this checkpoint; the retail oracle independently
continues to frame 1200 and observes the first seven live Enemy bullets at
frame 1180. The replay-only OpenVM workload executes 28,003,469 instructions
and 1,089,931,880 metered cells and exposes digest
`7d70502eb31b1ad8fc13947b8ae68185df92f3799ee62ca033b21c78fd114281`.

A first owner-local Lean model now machine-checks why active-only Effect slots
violate one-step noninterference and how a narrow dormant reuse shadow repairs
that modeled allocation step. It is a proof-design result, not a whole-game or
C++-binding theorem. A second small definition decodes the audited target and
D3DX toward-zero x87 profiles and their SoftFloat configuration correspondence
without yet claiming complete arithmetic semantics.
A finite-input exception model separately checks why denormal signaling must
follow opcode priority rather than a single operand-class rule.
Comparison truth tables now cover all eleven status-mask/branch forms at the
244 mapped game comparison sites. A local extraction probe also executes the
verified 117-byte `__ftol2` body without retaining proprietary bytes and checks
its EDX:EAX truncation result over a bounded canonical domain; neither result
is yet a code-binding or reachable-range proof.
The 244 comparison addresses and 77 conversion-call addresses are now frozen
in a hash-bound, proprietary-byte-free obligation ledger. Every site remains
explicitly unclassified until it receives either a retained-operation
refinement or an omitted-path noninterference proof.
A derived source/sink ledger conservatively identifies 68 helper calls as
omission candidates and nine as gameplay-retained candidates. For the retained
ECL call, a pinned dispatch audit and Lean bit-vector theorem reduce the
observable result to one of 25 variable IDs (`-10025..-10001`) or the unchanged
literal path. This narrows a future proof obligation; it does not yet discharge
source/binary correspondence, helper semantics, reachability, or guest binding.
The other eight retained calls are now bound to four point-item score blocks.
A conditional Lean model derives a `-4..452` collected-item interval and safe
score arithmetic, while a sealed Linux probe found 2,081 finite corpus
collections inside that interval. A total rational/exceptional model now avoids
assuming that item positions are finite: infinities cannot overlap a finite
player box, while NaN reaches the helper's modeled invalid low-EAX result zero
and selects the bounded top-score branch. A new 95-instruction player-position
audit and total Lean clamp model show that the retail lower/upper clamp restores
the `16..432` center invariant even from either infinity; only NaN bypasses both
assignments. This replaces the blanket finite-player premise with explicit
candidate-not-NaN, writer-completeness, scheduling, binary/x87-binding, and
guest-refinement obligations. A dependent fixed-data audit independently walks
8,384 subroutine instructions from the seven hash-pinned retail ECL files. It
finds no player-position output among 1,844 candidate writers; importantly, all
80 increment/decrement instructions using the two handlers that bypass the
readonly type guard target only four local-variable IDs. Archive extraction,
non-ECL alias completeness, and guest binding are still explicit obligations.

## Repository boundary

The zkTH06 work lives at the repository root. The reconstructed game engine is
kept as a supporting snapshot rather than as this repository's history:

- `zkvm/` contains the first sliced kernel and defines the future guest/public-
  input boundary, including the OpenVM adapter;
- `formal/` records the refinement theorem and machine-checking obligations;
- `arithmetic/` contains exact-arithmetic experiments and their evidence
  boundaries;
- `evidence/` contains compact, proprietary-byte-free summaries of sealed
  local retail/reference comparisons;
- `docs/` records the differential methodology and milestone evidence;
- `paper/` is the living English LaTeX research paper and decision history;
- `tools/` contains format and comparison tooling owned by zkTH06;
- `replays/` contains redistributable fixtures and provenance for local-only
  inputs;
- `reference/` contains the adapted TH06 engine and compatibility runner.

The `reference/` snapshot has no imported Git ancestry. Its exact upstream
revisions, modifications, licenses and limitations are recorded in
[`reference/PROVENANCE.md`](reference/PROVENANCE.md).

This repository contains no original game executable, DAT archive, music,
third-party replay file, or other proprietary game asset.

## Proof statement under development

Given public commitments to:

- the target executable/data version and gameplay-kernel revision;
- the initial gameplay state and requested route/difficulty;
- a private replay or equivalent frame-input stream;

prove that one canonical state machine applies every input in authentic frame
order and reaches an accepted terminal state. Stage transitions, resources,
score, rank, RNG and retry state must be derived from live state rather than
trusted from replay checkpoints.

This proves valid execution of an input sequence. It does not prove that the
inputs were produced by a human or without external tools.

## Roadmap

### M0 — replay differential runner

- Strictly parse and validate TH06 v1.02h `.rpy` files.
- Inject the complete replay input mask at the authentic calc-chain priority.
- Export canonical binary frame snapshots using stable slot identities and raw
  floating-point bits.
- Compare a pinned replay frame by frame against an original/exact-reference
  exporter and report the first differing subsystem and field.
- Pass Normal no-miss/no-bomb, death/bomb, dialogue, all shot types, Lunatic,
  spell-heavy and Extra cases.

The first 2,000-frame Normal anchor is complete for its enhanced 50-field
projection. Its enclosing player-state subprojection drives 1,999 transitions
from a fixed post-calc anchor, checks the life-state change at frame 240, and
now checks focus/previous-input/fire-timer recurrence and the nested local
`SpawnBullets` and Player-bullet lifecycle projections. A linked prefix now
carries the complete 80-slot pool through all five deaths of the first Enemy
wave at frame 229 without slot-, collision-, or Enemy-state witnesses.
The full canonical subsystem projection and broader replay matrix remain open.

### M1 — canonical gameplay kernel

- Constrain stage 2–6 replay snapshots to state derived from prior stages.
- Remove rendering/audio/presentation work only after dependency and shared-RNG
  shadow behavior has been proven equivalent.
- Freeze a versioned transition function and acceptance predicate.

### M2 — zk execution

- Profile entity/state width, x87-compatible arithmetic/trigonometry and proof
  length independently.
- Prove one spell, then Stage 6, then a complete stage.
- Chunk or recursively aggregate a full six-stage run only after the smaller
  statements pass differential tests.

The stronger shooting-cadence 1,999-transition profile is now proven with
OpenVM v2.0.1. Its private payload is still 4,018 bytes rather than the earlier
95,976-byte environment transcript, and the hash-bound statement costs
211,737,944 metered cells. Local application proving took 75.57 seconds with
49,103,488 KiB peak RSS, and verification took 0.11 seconds. The tracked proof,
verifying key, vm executable, source bindings, negative checks, and explicit
claim boundary are in
[`evidence/openvm-player-shooting-1999-v1.json`](evidence/openvm-player-shooting-1999-v1.json).
The next local slice is also proven: 1,590 Reimu-A callback invocations produce
422 hash-committed bullets in 7,394,181 instructions and 309,751,316 metered
cells. Proving took 98.60 seconds with 51,626,064 KiB peak RSS and verification
took 0.12 seconds. The exact proof bundle and its cross-call limitation are in
[`evidence/openvm-player-bullets-1590-v1.json`](evidence/openvm-player-bullets-1590-v1.json).
The enclosing successor now derives 206 consecutive Player/bullet transitions
from a fixed empty pool and 436 bytes of replay-only private input. It initializes
35 bullets, reclaims 30, meters 474,516,189 cells, and has a tracked application
proof described in
[`evidence/openvm-player-bullet-lifecycle-206-v1.json`](evidence/openvm-player-bullet-lifecycle-206-v1.json).
The next enclosing successor crosses the frame-208 boundary with only two more
private bytes. It derives five early Stage-1 enemies, 200 damage calls, one
collision and death, target selection, and score 390 in 19,787,280 instructions
and 769,444,525 cells. Proving took 203.58 seconds with 52,632,376 KiB peak RSS;
verification took 0.22 seconds. The exact bundle and remaining x87/slicing
obligations are in
[`evidence/openvm-early-gameplay-207-v1.json`](evidence/openvm-early-gameplay-207-v1.json).
The complete first-wave successor executes 228 transitions from the same fixed
anchor using 480 replay-only private bytes. It derives five collisions/deaths,
253 damage calls, score 1950, and an empty first-wave Enemy pool, while publicly
committing every active bullet and Enemy projection. It meters 1,104,665,874
cells; proving took 299.07 seconds with 51,442,624 KiB peak RSS and verification
took 0.28 seconds. The exact bundle is in
[`evidence/openvm-first-wave-228-v1.json`](evidence/openvm-first-wave-228-v1.json).
The next successor closes the death-Item feedback at frame 249: one derived
small-power Item increases score to 1960, power to 1, and subrank to 1. Its 248
replay-only transitions meter 1,146,265,201 cells, and the exact proof bundle is
in [`evidence/openvm-first-item-248-v1.json`](evidence/openvm-first-item-248-v1.json).
The second-wave successor now reaches frame 350 with derived Enemy/ECL,
death-effect RNG, random-drop Item, and explicitly empty Enemy-bullet state.
Its 724-byte replay-only input meters 1,089,931,880 cells; the exact proof
bundle is in
[`evidence/openvm-second-wave-349-v1.json`](evidence/openvm-second-wave-349-v1.json).
The next kernel extension targets the first live Enemy-bullet spawn at frame
1180; Player death/respawn and bomb paths remain subsequent subsystem
boundaries.
Deriving the post-calc anchor, external time-stop writers, and
non-full-speed timer paths remain soundness gates rather than hidden premises.

The source audit and compatibility risks are in
[`docs/initial-analysis.md`](docs/initial-analysis.md). Current corpus results
and open gates are in [`docs/m0-progress.md`](docs/m0-progress.md). Replay
fixture sources, redistribution status and hashes are in
[`replays/README.md`](replays/README.md). The required retail-data identity and
local import procedure are in [`data/README.md`](data/README.md). The evolving
canonical digest protocol and its evidence boundary are in
[`docs/canonical-trace.md`](docs/canonical-trace.md); the proof-oriented field
and reuse audit is in
[`docs/state-projection-audit.md`](docs/state-projection-audit.md).
The pinned executable's x87/XMM census, control-word evidence, helper-call
surface, and exact-versus-refined arithmetic plan are in
[`docs/arithmetic-audit.md`](docs/arithmetic-audit.md). The reproducible pinned
SoftFloat differential probe and its deliberately narrower claim are in
[`arithmetic/README.md`](arithmetic/README.md); the address-to-proof bridge and
its still-open premises are in
[`docs/arithmetic-obligations.md`](docs/arithmetic-obligations.md). Research
questions, method and evaluation are maintained in
[`paper/main.tex`](paper/main.tex).

## Reference runner

Build the adapted engine on Debian or Ubuntu:

```sh
sudo apt install build-essential libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev
cd reference
premake5 gmake --no-asoundlib
make -C build config=release -j4
```

Validate a v1.02h replay without proprietary game data:

```sh
reference/th06 --replay-info /path/to/th6_*.rpy
```

Compatibility playback must be launched with a user-supplied Japanese game
data directory as its working directory:

```sh
/path/to/zkTH06/reference/th06 --headless \
  --replay /path/to/th6_ud0001.rpy --max-ticks 200000 \
  --canonical-trace trace.canonical.bin
```

The C++ validator checks the byte transform, checksum, version, metadata,
stage bounds, full input masks, frame ordering and playback sentinels. Playback
uses the original callback order, but still restores untrusted per-stage replay
snapshots in compatibility mode. See [`reference/README.md`](reference/README.md)
for the full protocol.

The target executable is Japanese TH06 v1.02h with SHA-256:

```text
9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245
```

Never commit or redistribute the supplied game directory, generated traces, or
third-party replay corpus.

With a verified local retail directory and a windowed launcher configuration,
the address-bound smoke/differential probe is:

```sh
python3 tools/run_retail_anchor.py \
  --retail-dir /path/to/th06 \
  --replay replays/samples/th6_ud002677.rpy \
  --output local/retail-anchor.jsonl --frames 2000

(cd /path/to/th06 && /path/to/zkTH06/reference/th06 --headless \
  --replay /path/to/zkTH06/replays/samples/th6_ud002677.rpy \
  --max-ticks 2000 --trace /path/to/zkTH06/local/reference-anchor.jsonl)

python3 tools/compare_retail_anchor.py \
  local/retail-anchor.jsonl local/reference-anchor.jsonl --player-bullets
```

The probe requires Wine, Xvfb, GDB, passwordless local `sudo` for ptrace, and a
Japanese UTF-8 locale. It verifies the executable/DAT hashes before launch and
keeps the commercial files in an isolated temporary runtime directory.

## License

Distributed under GPL-3.0. The imported reference snapshot also contains work
derived from the CC0 reconstruction; see
[`reference/PROVENANCE.md`](reference/PROVENANCE.md) and [`LICENSE`](LICENSE).

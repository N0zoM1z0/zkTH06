# TH06 zkVM initial source and feasibility analysis

Date: 2026-08-09

## Executive conclusion

The project is feasible as a staged engineering effort, but the existing Linux
headless fork is an acceleration/RL harness rather than a replay verifier.  It
is deterministic on this Linux build, but it does not yet establish gameplay
equivalence with the shipped Windows executable.  The first milestone should
therefore be an exact, differential replay runner.  Circuit design should
start only after that runner passes representative full replays.

The intended statement is stronger than "the ECL scripts ran": starting from a
committed TH06 v1.02h initial state, a private frame-input stream advances one
canonical gameplay state machine to an accepted terminal state.  Per-stage
replay snapshots must be checked against the state derived by the preceding
stage, not accepted as fresh trusted state.

## Inputs pinned locally

### Source repositories

| Repository | Local path | Pinned revision | Role |
| --- | --- | --- | --- |
| `GensokyoClub/th06` | `repos/th06` | `cc475a0bc3fef38683b0f02224c87ddba0a021d9` | Reverse-engineered v1.02h source/specification and matching work |
| `N0zoM1z0/th06-headless` | `repos/th06-headless` | `294a4784631161306792776e51770859d0529fb3` | Linux deterministic-execution spike |

`th06` is a reconstruction project, not an official source release.  At this
revision its published progress is approximately 97.65% implemented and 97.51%
byte-accurate.  That makes it extremely valuable, but remaining mismatches must
be closed or bounded before calling the zk semantics identical to v1.02h.

The reconstruction is CC0.  The portable/headless fork is GPLv3; copying or
deriving the proof kernel from it has GPL distribution implications.

### Original game

The supplied RAR has SHA-256:

`6b013b24c101ae846b97a2778abf461d537640611a835824a42533c692be55d6`

Its `th06.exe`/`東方紅魔郷.exe` has SHA-256:

`9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245`

This is the exact Japanese v1.02h executable hash required by the reconstruction
project.  The archive contains no `.rpy`.  A minimal working set was extracted
under ignored `local/original-th06/`; it is proprietary and must not be
committed or redistributed.

Data archive hashes:

| Archive | SHA-256 |
| --- | --- |
| `紅魔郷CM.DAT` | `a899853d04e214ae4df8090bad7fd42698527027aa9dfccb4650fbb1d7828a0a` |
| `紅魔郷ED.DAT` | `3fbb51f00785c98d6b4141a7a5a303f5955df3d181d2f220c2c6e81d717e9fee` |
| `紅魔郷IN.DAT` | `65d7ee9c4303bcb39f5f08a0ceaf7004e47fccc8242fd73db54b31a911f41af0` |
| `紅魔郷MD.DAT` | `8f8db1918842857a63eb7c76e7f971fb931203a6239c26828304fa3ce12da911` |
| `紅魔郷ST.DAT` | `0f834a35aef2d73b05cffecc830c017dacbcc6f11b9a0611a9da2f3970a112e7` |
| `紅魔郷TL.DAT` | `c05f4fa755602f9369d7cebd5689cf3655ec81bb746f5b269ee0faf3d5f0a020` |

### Replays

Four valid six-stage v1.02h samples are pinned under `replays/samples/`: three
Lunatic runs and one Normal no-miss/no-bomb full-spell run.  Provenance and
hashes are in `replays/README.md`.  The included `tools/replay_info.py` validates
and decodes the format without third party dependencies.

## What the source confirms

### Frame ordering is part of the semantics

The calc chain runs in ascending priority.  Relevant priorities are:

1. Game manager (`4`)
2. Replay input injection (`5`)
3. Stage (`6`)
4. Player (`7`)
5. Enemy/ECL (`9`)
6. Effects (`10`)
7. Bullets and items (`11`)
8. GUI/dialogue (`12`)
9. Screen effects (`14`)
10. Replay recording (`15`)

A verifier must preserve this order, including restart/skip behavior during
dialogue.  A simplified "one ECL step, then collisions" loop is not equivalent.

### Replay files are witnesses, not trusted checkpoints

`ReplayData` stores character/shot, difficulty, final score and seven stage
offsets.  Each stage block stores that stage's end score plus a start snapshot
of RNG seed, point count, power, lives, bombs, rank and the power-item counter,
followed by run-length input changes.  Playback restores the start snapshot at
every stage boundary and obtains the running score from the preceding block.
The file's reversible byte transform and additive checksum are not
cryptographic authentication.

For proof mode, stage 2 through 6 snapshots must either be ignored or constrained
to equal the state derived from the prior stage.  Otherwise a witness can forge
lives, bombs, power, rank, score, or RNG seed at each boundary.

### ECL is not a closed subsystem

Enemy update interleaves timeline ECL, movement, ANM execution, collision,
damage, death callbacks, item drops, effects and timers.  Bullet lifecycle can
depend on ANM script completion.  The same global RNG is consumed by ECL,
bullets, items, enemy logic, effects/particles, screen shake, bomb logic and
random ANM sprite selection.  Removing "visual" consumers without retaining
their RNG and state side effects desynchronizes later gameplay.

Skipping the draw chain also needs a proof-oriented audit.  Draw callbacks write
state such as `isInGameMenu`, `skyFogNeedsSetup`, spell-background ANM state,
laser VM fields, player/bomb VM positions and colors.  Some are render-only and
some may feed later ANM updates; the safe optimization is a tested shadow update,
not an unconditional deletion.

### Floating point is a compatibility gate

The v1.02h reconstruction uses x87 operations such as `fsincos` and `frndint`.
The portable/headless base replaces important paths with `std::sin` and
`std::cos`, and also uses host square root behavior.  A repeatable Linux result
can therefore still diverge from the 32-bit Windows executable.  The reference
runner must pin x87 control state and compare raw floating-point bits at the
first divergent frame.  The circuit semantics should be derived from those
measurements, including actual spill/extended-precision behavior.

## Headless fork assessment

The headless delta is small and useful: it adds direct Practice startup, fixed
seed, movement actions, an optional always-shoot flag, step mode, JSONL trace,
and removes pacing/render calls.  It does not consume `.rpy` files.

Current gaps for verification:

- It starts one Practice stage from fixed defaults instead of running a full
  game with derived stage continuity.
- Its action vocabulary cannot independently encode Shoot, Bomb, Focus,
  dialogue Skip and direction on each frame.
- Its trace omits allocation slot identities and major state: player power and
  rank, items/player bullets, detailed enemy/ECL state, ECL PCs/stacks/registers,
  dialogue, ANM/effects, and several timers/flags.
- Decimal JSON is convenient for inspection, but the differential digest should
  serialize canonical integer fields and raw float bits, with no pointers,
  padding, locale, or unstable ordering.
- It explicitly stops on the first physical hit by default, whereas authentic
  replay semantics include deaths, bombs and respawns.

The fork built successfully on this host.  Two independent Stage 6, Lunatic,
Reimu A, seed 7, auto-shoot runs of 600 ticks produced byte-identical JSONL:

`aeac29aa6348d7060036221a29f307963132e279855a080b0efbf5100651f142`

Each run took about 0.30 seconds wall time and about 38 MiB RSS when run in
parallel.  This is evidence of same-host self-determinism and useful speed, not
evidence of v1.02h equivalence.

## Recommended gates

### M0: Exact replay differential runner

1. Add strict `.rpy` parsing: bounds, version, checksum, stage layout and exact
   frame masks.
2. Add compatibility playback that injects replay masks at calc priority `5`
   and initially restores the game's stage snapshots so it can be compared to
   the original behavior.
3. Add a separate canonical-proof mode that derives cross-stage state and
   constrains every supplied snapshot rather than trusting it.
4. Export a canonical binary state digest every frame.  Include stable slot
   indices, all gameplay state, RNG seed/count, ECL timeline and per-enemy VM
   state, input/dialogue state, and the required ANM/effect shadow state.
5. Build a Windows/original executable exporter or an exactly matched
   reconstruction runner and compare the same replay frame by frame.  Triage
   the first differing subsystem and field; never compare only final score.
6. Pass a matrix containing the current Normal no-miss/no-bomb and Lunatic
   replays plus bomb/death, dialogue-skip, all character/shot types, Extra and
   spell-heavy cases.

### M1: Canonical gameplay kernel

Freeze a versioned state transition only after M0 passes.  Remove rendering,
audio and presentation data one subsystem at a time, retaining dependency/RNG
shadow semantics and rerunning the entire differential corpus after each cut.
Commit the executable hash, data hashes, kernel version, initial state and replay
commitment in the public statement.

Acceptance should be derived from live state: requested difficulty/route,
stages reached in order, no retry/continue if that is part of the claim, and the
actual Stage 6 clear state.  It proves a valid input execution, not human play
and not absence of tool assistance.

### M2 and later: zk implementation

Start with one spell or one stage, then Stage 6 no-miss/no-bomb, then a full
stage, and only then recursive/chunked proofs for all six stages.  Profile three
separate cost centers before choosing the backend: entity/state width, x87-like
floating point/trigonometry, and proof length/recursion.  A narrow zkECL circuit
is still useful as a component test, but it cannot by itself prove a real replay.

## Immediate implementation target

The next code change should be `.rpy` playback plus a binary state exporter in
the headless fork, not a circuit.  The first concrete acceptance criterion is:

> For one pinned replay and the exact original data, both the v1.02h reference
> runner and Linux runner produce the same canonical state digest at every
> gameplay frame, or the tooling identifies the first divergent field.

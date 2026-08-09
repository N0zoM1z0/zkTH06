# zkTH06

Replay-verified Touhou 6 gameplay semantics for zero-knowledge execution.

The goal is to prove that a private frame-input stream advances a committed
Touhou Koumakyou v1.02h gameplay state machine from a canonical initial state to
an accepted result. Before freezing a zkVM guest, the project must first make
that state machine agree frame-for-frame with the shipped 32-bit Windows game.

> **Evidence boundary:** an address-bound Wine probe now matches the shipped
> executable and Linux reference for a 34-field raw gameplay projection over
> the first 2,000 frames of one tracked replay. This is finite differential
> evidence, not whole-state equivalence. The current runner remains an
> instrumented reference harness, not final proof semantics.

The first proof-oriented executable slice is now present under `zkvm/`: an
integer-only implementation of the PC24 player-position update whose inputs and
outputs remain raw binary32 bits. It matches 1,999 consecutive transitions
derived from the retail anchor. This freezes a narrow, fail-closed experiment,
not a complete gameplay guest or a formal refinement theorem.

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
  input boundary;
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

The first 2,000-frame Normal anchor is complete for its 34-field projection,
and its player-position subprojection drives a 1,999-transition integer PC24
kernel test. The full canonical subsystem projection and broader replay matrix
remain open.

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
  local/retail-anchor.jsonl local/reference-anchor.jsonl
```

The probe requires Wine, Xvfb, GDB, passwordless local `sudo` for ptrace, and a
Japanese UTF-8 locale. It verifies the executable/DAT hashes before launch and
keeps the commercial files in an isolated temporary runtime directory.

## License

Distributed under GPL-3.0. The imported reference snapshot also contains work
derived from the CC0 reconstruction; see
[`reference/PROVENANCE.md`](reference/PROVENANCE.md) and [`LICENSE`](LICENSE).

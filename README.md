# zkTH06

Replay-verified Touhou 6 gameplay semantics for zero-knowledge execution.

The long-term goal is to prove that a private frame-input stream advances a
committed reconstruction of Touhou Koumakyou 1.02h from its canonical initial
state to an accepted gameplay result.  The current milestone is deliberately
earlier: build an exact replay runner and find the first state divergence from
the shipped 32-bit Windows executable before freezing any zkVM semantics.

This repository starts from
[`N0zoM1z0/th06-headless`](https://github.com/N0zoM1z0/th06-headless), itself a
portable/headless fork of
[`GensokyoClub/th06`](https://github.com/GensokyoClub/th06).  It contains no
original game executable, DAT archive, music, replay corpus, or other
proprietary game asset.

> **Evidence boundary:** same-host deterministic Linux execution is working.
> Bit-for-bit gameplay equivalence with the shipped executable has not yet been
> established.  Until the differential gate passes, this code is an
> instrumentation and acceleration harness, not the final proof semantics.

## Proof statement under development

Given public commitments to:

- the target executable/data version and gameplay-kernel revision;
- the initial gameplay state and requested route/difficulty;
- a private replay or equivalent frame-input stream;

prove that one canonical state machine applies every input in authentic frame
order and reaches an accepted terminal state.  Stage transitions, resources,
score, rank, RNG and retry state must be derived from live state rather than
trusted from replay checkpoints.

This proves valid execution of an input sequence.  It does not prove that the
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

The source audit and concrete compatibility risks are recorded in
[`docs/initial-analysis.md`](docs/initial-analysis.md).  Replay fixture sources
and hashes are recorded in [`replays/README.md`](replays/README.md); downloaded
replays are intentionally excluded from Git.

## Current headless harness

The inherited harness can start Practice Stage 1–6 directly, accept fixed-seed
movement actions, run without frame pacing/rendering and write JSONL traces.
See [`HEADLESS.md`](HEADLESS.md) for its current protocol and limitations.

Validate a v1.02h replay without loading proprietary game data:

```sh
./th06 --replay-info /path/to/th6_*.rpy
```

The C++ validator checks the byte transform, checksum, version, character and
difficulty bounds, monotonic stage offsets, block sizes, complete input masks,
frame ordering and a bounded playback sentinel for every populated stage.

Build on Debian or Ubuntu:

```sh
sudo apt install build-essential libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev
premake5 gmake --no-asoundlib
make -C build config=release -j4
```

Run the current deterministic smoke case from a user-supplied Japanese data
directory:

```sh
./th06-headless --headless --seed 7 --max-ticks 600 \
  --practice-stage 6 --difficulty 3 --character 0 --shot-type 0 \
  --trace trace.jsonl --auto-shoot
```

The target executable is Japanese TH06 v1.02h with SHA-256:

```text
9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245
```

Never commit or redistribute the supplied game directory, generated traces, or
third-party replay corpus.

## License and attribution

This repository retains the GPL-3.0 license and history of the portable/headless
fork.  The underlying reconstruction work comes from GensokyoClub and its
contributors; see Git history and [`LICENSE`](LICENSE).

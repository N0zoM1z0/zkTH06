# Adapted TH06 reference runner

This directory is a source snapshot used to develop and test zkTH06 semantics.
It is supporting reference code, not the zkVM guest. See
[`PROVENANCE.md`](PROVENANCE.md) for its pinned sources and local changes.

Run build commands from this directory. The Linux headless mode supports
deterministic simulation experiments:

```sh
./th06 --headless --seed 7 --max-ticks 3600 \
  --practice-stage 6 --difficulty 3 --character 0 --shot-type 0 \
  --actions actions.txt --trace trace.jsonl --auto-shoot
```

`--headless` forces SDL's dummy video and audio drivers, disables music and
sound effects, fixes frameskip to zero, skips the draw chain and buffer swaps,
and advances the calc chain without wall-clock frame pacing. `--seed` accepts a
16-bit initial game RNG seed. `--max-ticks` bounds successful calc-chain ticks;
zero means unlimited. Headless runs do not overwrite the user's game config.

Direct Practice startup accepts stages 1 through 6, difficulty 0 through 3,
and the two character and shot-type indices. It reproduces the state transition
made by the generic Practice menu rather than automating the menu. An action
file contains either one action per line or `<repeat-count> <action>`. The
accepted vocabulary is the repository's 18 movement actions (`stay`, the eight
directions, and their `_fast` variants). Bomb is not representable; malformed,
unknown, forbidden, or exhausted action streams fail closed. `--auto-shoot`
adds Shoot without changing the movement action. `--trace` writes one JSON
record per logic tick with player state, RNG state, bullets, lasers, and enemies.

The default episode stops on the first physical HIT and emits
`"terminal_reason":"physical-hit"`. `--continue-after-hit` is an explicit
simulation-only override for studies that need the shipped respawn behavior.

For an online learner, replace `--actions ... --trace ...` with `--step`.
The process emits the initial JSON observation on stdout, accepts one action
line on stdin, advances one logic tick, emits the next observation, and repeats.
Diagnostics stay on stderr. Run-length action lines remain available, although
one action per line is the simplest lockstep protocol.

This still needs the original Japanese TH06 data archives. Those proprietary
files are not part of this repository and must never be committed.

Replay files can be inspected without the game archives:

```sh
./th06 --replay-info /path/to/th6_ud0001.rpy
```

This standalone mode fails closed on invalid magic, byte transform/checksum,
version, metadata, stage bounds, input masks, frame ordering or missing playback
sentinels.

Compatibility playback starts directly from the first populated replay stage:

```sh
./th06 --headless --replay /path/to/th6_ud0001.rpy \
  --max-ticks 200000 --trace replay.jsonl
```

ReplayManager injects the complete recorded mask at its original calc priority
and handles dialogue restart behavior. Replay mode does not stop on deaths; it
follows the replay through bombs, deaths and respawns until the game returns to
the replay menu. `replay-complete` is a playback terminal, not yet a proof
acceptance predicate.

For deterministic differential work, `--canonical-trace` writes one fixed-size
binary digest record per gameplay tick:

```sh
./th06 --headless --replay /path/to/th6_ud0001.rpy \
  --max-ticks 200000 --canonical-trace replay.canonical.bin
python3 ../tools/canonical_trace.py replay.canonical.bin
```

The revision-0.2 writer uses raw float bits, stable slot identities, relative
script offsets, and selected future-live ANM control state. It fails closed on
output errors. It remains a selected-field diagnostic rather than a complete
state commitment; see
[`../docs/canonical-trace.md`](../docs/canonical-trace.md) and
[`../docs/state-projection-audit.md`](../docs/state-projection-audit.md).
The pinned executable's address-level floating-point census and the reason host
`libm` is not accepted as proof semantics are in
[`../docs/arithmetic-audit.md`](../docs/arithmetic-audit.md).

On x86 and x86-64 the headless trigonometric wrapper executes x87 `fsincos`
under control word `0x007f` and restores the caller's word. This matches the
retail arithmetic path and removes a one-bit curved-Enemy velocity divergence
that host `std::sin`/`std::cos` exposed at gameplay frame 880. Other hosts keep
the compatibility fallback and are not an exact arithmetic oracle for that
path.

Compatibility mode restores each stage snapshot exactly as the shipped game
does. A later canonical-proof mode must instead derive cross-stage state and
constrain every supplied snapshot.

## Evidence boundary

The lockstep protocol is sufficient for an external RL environment wrapper,
and repeated Linux runs have produced byte-identical traces with original
Japanese data. That establishes deterministic Linux execution, not equivalence
to the shipped executable.

The next hard gate is replay/action-stream differential testing against a
Windows exporter using the same data, scope, seed, and actions. Multi-process
orchestration must also impose explicit CPU and memory limits. Until the
differential gate passes, use this mode as an acceleration harness and keep the
shipped Windows game as final physical-run evidence.

The initial local corpus gate contains four six-stage v1.02h files. All four
reach `replay-complete`; their final Stage 6 frame and computed score match the
replay terminal metadata, including a Normal no-miss/no-bomb run and three
Lunatic runs. This is useful Linux self-consistency evidence only.

# Headless logic-mode spike

This branch contains a Linux headless mode intended for deterministic
simulation experiments:

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

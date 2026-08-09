# M0 replay differential runner progress

Last updated: 2026-08-09

## Implemented

- Standalone strict v1.02h replay validation with `--replay-info`.
- Bounds-checked decoded stage views and a playback cursor capped by the first
  valid `9999999` sentinel.
- Direct headless compatibility playback with `--replay`.
- Complete replay masks (Shoot, Bomb, Focus, Skip and four directions) injected
  by the existing ReplayManager at calc priority 5.
- Replay deaths, bombs and respawns continue rather than using the RL harness's
  first-hit terminal.
- Deterministic terminal summaries and `replay-complete` detection.

Compatibility playback intentionally restores every per-stage replay snapshot,
matching shipped playback. It is an oracle-development mode, not the future
canonical-proof mode.

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

## Remaining M0 gates

1. Replace inspection-oriented JSON with a versioned canonical binary frame
   snapshot and subsystem digests.
2. Include stable entity slot indices, raw float bits, ECL timeline/context,
   player bullets/items, dialogue and required ANM/effect shadow state.
3. Export the same schema from the original executable or an exact-reference
   build and identify the first differing field.
4. Fix x87/libm and skipped-draw semantic differences until the corpus is
   frame-identical.
5. Add canonical-proof playback that derives stage transitions and rejects a
   replay whose stage snapshots do not match live state.

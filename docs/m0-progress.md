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
- Canonical trace revision 0.2 with a fixed 592-byte frame record, eleven
  domain-separated subsystem digests, raw binary32 encoding, stable entity
  indices, relative script offsets, and fail-closed output handling.
- Real selected-field serializers for gameplay, ECL, Stage, GUI/message, and
  future-live owner-local ANM state, plus an independent Python validator,
  first-mismatch comparator, and payload statistics.

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

## Remaining M0 gates

1. Close or explicitly constrain the selected projection. Inactive Effect
   residue and dynamic ScreenEffect jobs are known open noninterference cases;
   see [`state-projection-audit.md`](state-projection-audit.md).
2. Add a field-level canonical snapshot at a selected tick so a subsystem
   mismatch can be reduced to its first field.
3. Export the same schema from the original executable or an exact-reference
   build and identify the first differing field.
4. Fix x87/libm and skipped-draw semantic differences until the corpus is
   frame-identical.
5. Add canonical-proof playback that derives stage transitions and rejects a
   replay whose stage snapshots do not match live state.

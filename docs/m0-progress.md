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
  EDX:EAX projection logic.

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
the preceding x87 operations are also inventoried.

The CRT trigonometric wrappers embed x87 control word `0x027f` (53-bit
significand precision, round-to-nearest-even, exceptions masked), but static
analysis has not proved the loader-established word at game entry. The exact
profile must therefore be measured and constrained explicitly. The complete
audit and soundness consequences are in
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
dyadic truncation and returned an empty x87 stack. These remain host-specific
counterexample searches: load exceptions, out-of-range helper inputs,
transcendentals, address binding, reachable-range invariants, and a
model-to-code proof remain open. The reproduction and claim boundary are in
[`../arithmetic/README.md`](../arithmetic/README.md).

## Remaining M0 gates

1. Close or explicitly constrain the selected projection. Inactive Effect
   residue and dynamic ScreenEffect jobs are known open noninterference cases;
   see [`state-projection-audit.md`](state-projection-audit.md).
2. Add a field-level canonical snapshot at a selected tick so a subsystem
   mismatch can be reduced to its first field.
3. Export the same schema from the original executable or an exact-reference
   build and identify the first differing field.
4. Record the entry x87/CPU profile, instrument reached arithmetic sites,
   cover load/remainder and exceptional helper behavior where reachable, prove
   the `__ftol2` signed-i32 input invariant, and replace host-libm behavior with
   an exact, address-bound arithmetic baseline; prove skipped-draw arithmetic
   noninterference before removing it.
5. Add canonical-proof playback that derives stage transitions and rejects a
   replay whose stage snapshots do not match live state.

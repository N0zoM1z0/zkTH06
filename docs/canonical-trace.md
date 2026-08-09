# Canonical digest trace protocol

Status: experimental wire revision 0.1. The C++ writer, Python validator, and a
cross-language synthetic fixture are implemented. Real gameplay-state payload
serializers are the next integration step; revision 0.1 must not be presented
as a complete state commitment.

## Purpose and claim boundary

A canonical trace is a compact differential diagnostic. Each gameplay frame
contains one digest for each ordered subsystem and a root digest over the
record. It is designed to identify the first frame and subsystem on which two
executions disagree.

The trace is not a proof, signature, or complete snapshot. Revision 0.1 carries
the `selected-fields` coverage flag. Equality therefore establishes equality
only for the serialized projection, under the collision resistance of SHA-256.
It does not establish equality of omitted state, fidelity to the shipped game,
or zkVM soundness. A field-level snapshot is still required to explain the
first subsystem mismatch.

## Encoding rules

- All integers have explicit widths and use little-endian encoding.
- Signed integers use two's-complement bit patterns.
- A Boolean is exactly one byte, `0` or `1`.
- A `float` is its raw IEEE-754 binary32 bit pattern; it is never formatted as
  decimal or numerically normalized. This preserves signed zero, NaN payloads,
  and one-bit rounding differences.
- Entity serializers retain stable array-slot order and encode slot indices.
- Pointer values, compiler padding, host container order, and locale-dependent
  representations are forbidden.

## File header

The header is 64 bytes.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | ASCII magic `ZKTH06CT` |
| 8 | 2 | major version |
| 10 | 2 | minor version |
| 12 | 4 | header size, currently 64 |
| 16 | 4 | frame-record size, currently 592 |
| 20 | 2 | subsystem count, currently 11 |
| 22 | 2 | header flags; bit 0 means selected-field coverage |
| 24 | 2 | initial RNG seed |
| 26 | 1 | difficulty |
| 27 | 1 | character |
| 28 | 1 | shot type |
| 29 | 1 | first stage |
| 30 | 1 | run mode: 0 unknown, 1 Practice, 2 Replay |
| 31 | 1 | reserved zero byte |
| 32 | 32 | SHA-256 of the schema descriptor |

Changing field meaning, subsystem payload order, hashing domains, or coverage
requires a new schema descriptor and version. A decoder rejects unknown sizes,
flags, versions, run modes, reserved bits, and schema digests.

## Frame record

The 32-byte prefix contains:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | runner tick |
| 8 | 4 | game frame |
| 12 | 4 | signed stage number |
| 16 | 2 | complete input mask |
| 18 | 1 | terminal-reason code |
| 19 | 1 | frame flags |
| 20 | 4 | signed Supervisor state |
| 24 | 8 | zero-based emitted-record index |

It is followed by eleven 48-byte subsystem records in this fixed order:

1. global
2. RNG
3. Player
4. player bullets
5. Enemy/ECL
6. enemy bullets
7. lasers
8. items
9. Stage
10. GUI/message
11. effects

Each subsystem record is `u16 id`, `u16 coverage flags`, `u32 entity count`,
`u64 serialized payload byte count`, and a 32-byte digest. The final 32 bytes
are the frame root.

Terminal codes are 0 for a nonterminal frame, 1 input error, 2 physical hit, 3
replay complete, 4 successful chain exit, 5 erroneous chain exit, 6 tick
limit, and 255 unknown.

## Domain-separated hashes

For subsystem identifier `id` and canonical payload `P`:

```text
SHA256("zkTH06-state-v0.1\0" || u16le(id) || P)
```

For the 560 record bytes before the root:

```text
SHA256("zkTH06-trace-root-v0.1\0" || record_without_root)
```

The byte count excludes the subsystem hash domain and identifier. It is useful
for detecting accidental projection changes even when an implementation cannot
emit raw state.

## Tools and tests

The reference binary generates a cross-language fixture and runs its internal
SHA/encoding checks:

```sh
reference/th06 --canonical-self-test fixture.bin
```

The Python tool validates the header, schema, subsystem order, record indices,
terminal codes, flags, exact file length, and every frame root:

```sh
python3 tools/canonical_trace.py fixture.bin
python3 tools/canonical_trace.py left.bin --compare right.bin
```

The comparison reports the first differing record and all differing subsystem
digests. CI also flips a byte in a temporary fixture and requires the validator
to reject it.

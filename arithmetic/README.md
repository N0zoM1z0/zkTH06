# Arithmetic experiments

This directory develops an exact arithmetic baseline before any zk-friendly
replacement is admitted. The current experiment compares x87 result bits,
exception-status bits, and comparison condition codes against Berkeley
SoftFloat across basic arithmetic and the dominant store/round/conversion/
branch boundaries. A separate local probe executes the exact `__ftol2` body
extracted from a verified retail image. Both are deterministic counterexample
searches, not proofs of arithmetic equivalence.

## Pinned SoftFloat oracle

The experiment uses [Berkeley SoftFloat Release
3e](https://www.jhauser.us/arithmetic/SoftFloat-3/doc/SoftFloat.html) from the
`ucb-bar/berkeley-softfloat-3` repository at commit:

```text
f74b1e48110ac3a27dd49b787d164e55e42d81d1
```

That commit is dated 26 January 2018 and titled `Release 3e`. SoftFloat source
is not vendored into zkTH06. Its checkout stays under the ignored `repos/`
directory, and the runner exports the pinned Git object into a temporary
directory before compiling. Working-tree modifications and build products are
therefore not probe inputs.

The upstream `COPYING.txt` is a three-clause BSD-style license with SHA-256:

```text
145ea96b4a4a04a1a7738d2a2bf9e830f861971e69606187b018d9e8fc0b95c7
```

The runner additionally checks hashes for the selected platform header,
public API header, and state implementation. It compiles only the 37 upstream
translation units needed by this experiment, using the `8086` specialization.

## Compared semantics

[`softfloat_probe.c`](softfloat_probe.c) first evaluates `add`, `sub`, `mul`,
`div`, and `sqrt` in two ways:

1. inline x87 instructions under control word `0x027f`; and
2. SoftFloat `extF80_*` operations with round-to-nearest-even and
   `extF80_roundingPrecision = 64`.

SoftFloat documents `64` here as precision equivalent to `float64_t`; that is
the 53-bit significand setting corresponding to x87 precision-control value
`10`. Results retain the extended exponent range. The comparison checks the
raw 16-bit sign/exponent and 64-bit significand after an x87 `fstpt` store.

The same probe then checks five instruction boundaries represented heavily in
the audited executable:

- `fstp` to binary32 and binary64;
- `frndint`; and
- `fistp` to signed 32-bit and 64-bit integers.

Each boundary is run under both `0x027f` (nearest-even) and `0x0e7f`
(toward-zero with the same PC53 precision and exception masks). The latter is
the control word produced when the audited D3DX `F2IBegin` helpers set the RC
bits. SoftFloat uses `softfloat_round_near_even` and
`softfloat_round_minMag`, respectively.

For every tuple, the probe also compares x87 status bits 0--5: invalid,
denormal operand, divide-by-zero, overflow, underflow, and inexact. SoftFloat's
five IEEE-style flags map directly to all except denormal operand. That sixth
bit is derived separately from the instruction and operand class. This is
instruction-specific: `frndint` can signal it, while `fistp` and `fstp` do not;
invalid square root and zero-divide also take priority for the tested arithmetic
forms. An earlier naive "any subnormal input" rule failed immediately on a
subnormal dividend divided by zero, so it was not retained.
The per-instruction rules are checked against Intel's
[Instruction Set Reference, Volume 2A](https://www.intel.com/content/www/us/en/content-details/850971/intel-64-and-ia-32-architectures-software-developer-s-manual-volume-2a-instruction-set-reference-a-l.html)
and AMD's
[x87 instruction manual](https://docs.amd.com/v/u/en-US/26569_3.16).

Finally, the probe mirrors the only comparison forms found in mapped game
code: `fcomp m32fp` and `fcomp m64fp`. It compares C0, C1, C2, and C3 together
with exception bits 0--5. The SoftFloat relation is built from signaling
equality and less-than so every NaN produces x87's unordered relation and
invalid exception. Fixed cases include infinities, quiet and signaling NaNs,
signed zeros, and combinations in which invalid takes priority over a
subnormal operand. Random comparison cases remain canonical and finite.

Two deterministic input classes are used for every operation:

- finite binary32 bit patterns converted exactly to `extFloat80_t`; and
- canonical finite extended values with the explicit integer bit consistent
  with the exponent and the low eleven significand bits zero, including
  boundary-heavy sampling across the full extended exponent range.

Fixed cases cover signed zero, subnormal boundaries, normal boundaries, values
around one, signed integer-conversion limits, and the largest finite values.
Random inputs exclude NaN and infinity encodings, although operations such as
zero divided by zero and square root of a negative finite value can still
produce a NaN result. Comparison-only fixed cases additionally cover canonical
infinities and both NaN classes.

## Reproduction

Create the ignored upstream checkout once:

```sh
git clone https://github.com/ucb-bar/berkeley-softfloat-3.git \
  repos/berkeley-softfloat-3
git -C repos/berkeley-softfloat-3 checkout --detach \
  f74b1e48110ac3a27dd49b787d164e55e42d81d1
```

Then run one million pseudorandom cases per operation and input class:

```sh
python3 tools/run_softfloat_probe.py --cases 1000000
```

The runner requires an x86-64 host, Git, and a C11 compiler. It records the
pinned revision, probe hash, architecture, CPU model, and compiler identity.
Compilation and execution take place in a temporary directory. This
external-source hardware experiment is intentionally not part of the
lightweight repository CI; CI checks the runner's Python syntax but does not
fetch SoftFloat or compile the C probe.

On the initial AMD EPYC 9654 host with GCC 11.4.0, probe SHA-256
`b062a031b5866b7e86514db17d162ecbdf9398b0a5d0c5530dfcf6c4889ffe71`,
the command produced:

| Family | binary32-derived tuples | canonical PC53 ext80 tuples | Mismatches |
| --- | ---: | ---: | ---: |
| five basic operations | 5,000,798 | 5,001,314 | 0 |
| five boundaries, two RC profiles | 10,000,140 | 10,000,330 | 0 |

It also matched 2,000,110 `fcomp m32fp` and 2,000,110 `fcomp m64fp`
condition/status tuples. The relation totals were 2,001,320 greater, 1,998,808
less, 16 equal, and 76 unordered. The deliberately small equal/unordered
counts come from fixed cases; random pairs almost never compare equal and
exclude NaNs.

In total, 34,002,802 result/condition/exception tuples matched. The run observed each of
the six exception bits in the basic-operation campaign:

| Campaign | Invalid | Denormal | Divide-by-zero | Overflow | Underflow | Inexact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| basic | 1,001,228 | 88,466 | 56 | 255,746 | 265,276 | 7,547,221 |
| boundaries | 3,150,469 | 20,789 | 0 | 1,815,764 | 1,853,992 | 10,475,625 |
| comparisons | 76 | 29,682 | 0 | 0 | 0 | 0 |

Counts overlap when one operation sets multiple flags; divide-by-zero does not
apply to the selected boundary instructions. The measured run used the
deterministic seed embedded in the probe and completed in 3.6 seconds. These
results are specific to that processor, compiler, source revision, probe hash,
selected operations, and input generator.

## Exact `__ftol2` extraction experiment

The static audit identifies 77 calls from mapped game functions to the helper
at virtual address `0x0045ba78`. The instruction immediately before each call
is x87: 60 `fld`, seven `fmul`, four `fdiv`, two `fadd`, two `fsubp`, and two
`fsubr`. A bounded straight-line use scan observes EAX at all 77 sites and EDX
at none; 75 sites observe all of EAX and two observe only AL. The scan stops at
branches or later calls and leaves EDX live at 42 stopping points, so this is a
bounded syntactic fact rather than whole-control-flow dead-result analysis or a
dynamic range proof.

[`run_ftol2_probe.py`](../tools/run_ftol2_probe.py) verifies the retail
executable hash, resolves the helper through the PE section table, and checks
the 117-byte body against SHA-256
`5333b186c02836974c6f792303aeb2c00d856316b93ccbbe65f51def6ae661b4`.
It places those bytes only in a temporary directory and links
[`ftol2_harness.S`](ftol2_harness.S) as a freestanding i386 process. No helper
byte, executable fragment, or generated object is retained or redistributed.

Run the local experiment with:

```sh
python3 tools/run_ftol2_probe.py \
  local/original-th06/東方紅魔郷.exe --cases 1000000
```

The local runner requires GNU `as`, GNU `ld`, and Linux i386 execution support;
it does not require 32-bit libc. Its PE addressing and dyadic decoder have a
proprietary-input-free unit test:

```sh
python3 tests/test_ftol2_probe.py
```

The independent Python model interprets each canonical finite ext80 input as
an exact dyadic rational and truncates it toward zero. Inputs are limited to
the signed-i64 representable domain and combine exact binary32-derived values,
canonical PC53 extended values, signed/subnormal/integer boundaries, and the
exact `-2^63` endpoint. On the initial host, all 1,000,014 complete EDX:EAX
results matched and every call returned the x87 stack to empty; 908,273 runs
left the inexact status bit set.

A second campaign exercised the observation made by ECL variable dispatch:
exact quarter-step boundaries around `-10025..-10001`, random PC53 values
densely covering that interval, infinities, both NaN classes, very large finite
values, a pseudo-denormal, and an unnormal. All 1,000,154 classifications
matched: 3,084 inputs selected one of the 25 variable IDs, and nine exceptional
inputs raised invalid without spuriously selecting an ID. The combined run
executed the exact helper 2,000,168 times with no mismatch.

The first campaign closes neither the out-of-range/NaN helper semantics nor a
call-site range proof, and the second remains finite counterexample search.
However, the ECL caller does not observe an arbitrary integer: it observes only
which, if any, of 25 sentinel IDs was selected. A replacement for that site can
therefore prove exact classifier agreement without first imposing a global
signed-32-bit range on every non-sentinel input. That narrower theorem still
needs raw-ext80/helper semantics and code binding. Other retained arithmetic
consumers may continue to require conventional range invariants. Until their
site-specific premises are proved, the exact extracted helper remains the
oracle.

## Address-level obligation ledger

[`obligations-v1.json`](obligations-v1.json) turns the aggregate census into a
reviewable proof-work queue. It records all 244 comparison addresses and all 77
mapped `__ftol2` call addresses, their mapped owner/offset, the minimum semantic
classification needed by the current Lean models, and conservative open-status
fields. It deliberately excludes executable bytes and full disassembly operand
strings.

[`arithmetic_obligations.py`](../tools/arithmetic_obligations.py) accepts only
the pinned executable/mapping/implemented hashes, invokes the same audit, and
seals canonical JSON with a content digest. The tracked ledger also records
the generator and audit-tool hashes. A local owner of the retail image can
check byte-for-byte reproduction with:

```sh
python3 tools/arithmetic_obligations.py \
  local/original-th06/東方紅魔郷.exe \
  --mapping repos/th06/config/mapping.csv \
  --implemented repos/th06/config/implemented.csv \
  --check arithmetic/obligations-v1.json
```

Public CI only runs the proprietary-input-free structural/digest test. The
ledger makes no reachability or refinement claim: every site is still marked
`unclassified`, and every conversion range remains `unproved`. The schema,
discharge discipline, and corrected two-site AL result are detailed in
[`docs/arithmetic-obligations.md`](../docs/arithmetic-obligations.md).

Two derived version-1 artifacts begin classifying that queue without modifying
its conservative base status:

- [`ftol2-source-candidates-v1.json`](ftol2-source-candidates-v1.json) assigns
  all 77 calls a source-expression candidate and semantic sink at authoritative
  source revision `cc475a0bc3fef38683b0f02224c87ddba0a021d9`. It identifies
  68 presentation/audio calls as candidates for omission after
  noninterference, and nine gameplay calls as retain candidates. These are
  manual disassembly/source alignments, not debug-line or compiler proofs.
- [`ecl-var-dispatch-v1.json`](ecl-var-dispatch-v1.json) verifies 17 critical
  instruction signatures and extracts the 25 unique in-function jump targets
  used by `GetVar`/`GetVarFloat`. It contains no executable bytes or complete
  operand strings. Its static decode is not yet a verified decoder,
  reachability, helper-refinement, or guest-binding theorem.

Both artifacts have proprietary-input-free structural tests in lightweight
CI. Local owners can reproduce them with:

```sh
python3 tools/ftol2_source_candidates.py \
  --source-root repos/th06 \
  --check arithmetic/ftol2-source-candidates-v1.json
python3 tools/ecl_var_dispatch_audit.py \
  local/original-th06/東方紅魔郷.exe \
  --mapping repos/th06/config/mapping.csv \
  --check arithmetic/ecl-var-dispatch-v1.json
```

## Soundness boundary

The experiment supports a candidate implementation choice; it does not close
the arithmetic proof. In particular:

- Berkeley SoftFloat is an independently implemented executable oracle here,
  not a formally verified theorem;
- basic/store operations compare only the six exception bits; comparisons add
  C0/C1/C2/C3, while TOP/tag state, instruction/data pointers, stack faults,
  trap behavior, and arbitrary NaN payload/noncanonical encodings remain
  outside the SoftFloat probe;
- binary32-derived values are first converted exactly and then loaded as
  extended values, so the status comparison does not model a preceding
  `fld m32fp` denormal-operand event;
- remainder and `fisttp` remain unmodeled; the extracted `__ftol2` experiment
  covers its complete register result and stack balance only for canonical
  finite, signed-i64-representable PC53 inputs; a second experiment tests only
  ECL sentinel classification on focused exceptional and boundary inputs, not
  universal exceptional semantics or a reachable-state theorem;
- x87 transcendental instructions are outside SoftFloat's operation set and
  still require a pinned processor/emulator profile or a separate equivalence
  proof;
- the experiment does not prove the game's loader-established control word,
  dynamic reachability, original instruction extraction, or connection to a
  future Lean definition and zkVM guest.

The address binding work queue is now explicit, but none of its entries is
discharged. Source/sink candidates narrow it to nine retained calls and 68
potential omissions; every omission still needs noninterference. The immediate
arithmetic goals are an exact ECL helper-to-classifier theorem, the collected
item-y range invariant for eight score calls, complete result-use evidence,
load/remainder semantics, and an exact transcendental profile. The exact
implementation remains the fallback whenever a refinement theorem cannot be
proved.

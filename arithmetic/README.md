# Arithmetic experiments

This directory develops an exact arithmetic baseline before any zk-friendly
replacement is admitted. The current experiment compares x87 result bits and
exception-status bits against Berkeley SoftFloat across basic arithmetic and
the dominant store/round/conversion boundaries. It is a deterministic
counterexample search, not a proof of arithmetic equivalence.

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
public API header, and state implementation. It compiles only the 32 upstream
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

Two deterministic input classes are used for every operation:

- finite binary32 bit patterns converted exactly to `extFloat80_t`; and
- canonical finite extended values with the explicit integer bit consistent
  with the exponent and the low eleven significand bits zero, including
  boundary-heavy sampling across the full extended exponent range.

Fixed cases cover signed zero, subnormal boundaries, normal boundaries, values
around one, signed integer-conversion limits, and the largest finite values.
Random inputs exclude NaN and infinity encodings, although operations such as
zero divided by zero and square root of a negative finite value can still
produce a NaN result.

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
`cf55d2ed7bde6c1020877b427eca43bc0f4e49f8ab7ffa29bfc4d8fdb487b392`,
the command produced:

| Family | binary32-derived tuples | canonical PC53 ext80 tuples | Mismatches |
| --- | ---: | ---: | ---: |
| five basic operations | 5,000,798 | 5,001,314 | 0 |
| five boundaries, two RC profiles | 10,000,140 | 10,000,330 | 0 |

In total, 30,002,582 result/exception tuples matched. The run observed each of
the six exception bits in the basic-operation campaign:

| Campaign | Invalid | Denormal | Divide-by-zero | Overflow | Underflow | Inexact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| basic | 1,001,228 | 88,466 | 56 | 255,746 | 265,276 | 7,547,221 |
| boundaries | 3,150,469 | 20,789 | 0 | 1,815,764 | 1,853,992 | 10,475,625 |

Counts overlap when one operation sets multiple flags; divide-by-zero does not
apply to the selected boundary instructions. The measured run used the
deterministic seed embedded in the probe and completed in 4.3 seconds. These
results are specific to that processor, compiler, source revision, probe hash,
selected operations, and input generator.

## Soundness boundary

The experiment supports a candidate implementation choice; it does not close
the arithmetic proof. In particular:

- Berkeley SoftFloat is an independently implemented executable oracle here,
  not a formally verified theorem;
- only the six exception bits of the x87 status word are compared; condition
  codes, TOP, tag word, instruction/data pointers, stack faults, trap behavior,
  and NaN payload policy for arbitrary NaN inputs remain outside the probe;
- binary32-derived values are first converted exactly and then loaded as
  extended values, so the status comparison does not model a preceding
  `fld m32fp` denormal-operand event;
- comparisons, remainder, `fisttp`, and complete helper ABIs such as `__ftol2`
  remain unmodeled; `fistp` agreement covers only one primitive inside that
  helper;
- x87 transcendental instructions are outside SoftFloat's operation set and
  still require a pinned processor/emulator profile or a separate equivalence
  proof;
- the experiment does not prove the game's loader-established control word,
  dynamic reachability, original instruction extraction, or connection to a
  future Lean definition and zkVM guest.

The intended next step is to cover comparison/condition-code sequences and the
complete `__ftol2` ABI, then bind each operation to audited original addresses
and a machine-checked definition. The exact implementation remains the
fallback whenever a fixed-point refinement theorem cannot be proved.

# Arithmetic experiments

This directory develops an exact arithmetic baseline before any zk-friendly
replacement is admitted. The first experiment compares basic x87 result bits
against Berkeley SoftFloat. It is a deterministic counterexample search, not a
proof of arithmetic equivalence.

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
public API header, and state implementation. It compiles only the 20 upstream
translation units needed by this experiment, using the `8086` specialization.

## Compared semantics

[`softfloat_probe.c`](softfloat_probe.c) evaluates `add`, `sub`, `mul`, `div`,
and `sqrt` in two ways:

1. inline x87 instructions under control word `0x027f`; and
2. SoftFloat `extF80_*` operations with round-to-nearest-even and
   `extF80_roundingPrecision = 64`.

SoftFloat documents `64` here as precision equivalent to `float64_t`; that is
the 53-bit significand setting corresponding to x87 precision-control value
`10`. Results retain the extended exponent range. The comparison checks the
raw 16-bit sign/exponent and 64-bit significand after an x87 `fstpt` store.

Two deterministic input classes are used for every operation:

- finite binary32 bit patterns converted exactly to `extFloat80_t`; and
- canonical finite extended values with the explicit integer bit consistent
  with the exponent and the low eleven significand bits zero, including
  boundary-heavy sampling across the full extended exponent range.

Fixed cases cover signed zero, subnormal boundaries, normal boundaries, values
around one, and the largest finite values. Random inputs exclude NaN and
infinity encodings, although operations such as zero divided by zero can still
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

On the initial AMD EPYC 9654 host with GCC 11.4.0, the command checked
5,000,798 binary32-derived results and 5,001,314 canonical PC53 extended-input
results without finding a mismatch. The measured run used the deterministic
seed embedded in the probe. This result is specific to that processor,
compiler, source revision, selected operations, and input generator.

## Soundness boundary

The experiment supports a candidate implementation choice; it does not close
the arithmetic proof. In particular:

- Berkeley SoftFloat is an independently implemented executable oracle here,
  not a formally verified theorem;
- only result bits are compared, not the x87 status word, denormal-operand flag,
  tag word, stack behavior, traps, or NaN payload policy for arbitrary NaN
  inputs;
- comparisons, remainder, `frndint`, integer conversions, binary32/binary64
  stores, and helper ABIs such as `__ftol2` remain unmodeled;
- x87 transcendental instructions are outside SoftFloat's operation set and
  still require a pinned processor/emulator profile or a separate equivalence
  proof;
- the experiment does not prove the game's loader-established control word,
  dynamic reachability, original instruction extraction, or connection to a
  future Lean definition and zkVM guest.

The intended next step is to extend the oracle to the reached store,
comparison, and conversion boundaries, then bind each operation to audited
original addresses. The exact implementation remains the fallback whenever a
fixed-point refinement theorem cannot be proved.

# TH06 v1.02h arithmetic audit

Last updated: 2026-08-09

## Status and claim boundary

The shipped game does not implement a single abstract operation called
"float." Its observable arithmetic depends on x87 register state, control-word
state, instruction selection, explicit binary32/binary64 stores, compiler spill
boundaries, conversion helpers, and transcendental approximations. Replacing
this with host `libm` or rounding every source-level operation to binary32 is
not an equivalence-preserving baseline.

This document is a static census of the pinned Japanese v1.02h executable. It
does not yet prove dynamic reachability, initial control-word state, or
equivalence of the Linux runner. Counts over the complete `.text` section are
upper bounds that include statically linked CRT and D3DX code. Counts attributed
to mapped `th06::` ranges are a smaller source-binding candidate, not yet the
proved gameplay slice.

## Reproducible inputs

The audit binds all three inputs by SHA-256:

| Input | SHA-256 |
| --- | --- |
| Japanese v1.02h executable | `9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245` |
| upstream `config/mapping.csv` | `0f20300d5b107b36c933a7f7dc448407ee5f01c5cd7faad132d406c023163191` |
| upstream `config/implemented.csv` | `07b448de3503a285f3464f618c7c384607050c0fff81e0642aa13968fcb61311` |

The executable is a PE32 Intel 80386 GUI image with entry point `0x0045d746`
and linker major version 7. The mapping inputs come from the pinned
GensokyoClub revision recorded in [`reference/PROVENANCE.md`](../reference/PROVENANCE.md).
With that checkout at `repos/th06` and a locally verified retail executable,
the report is reproduced by:

```sh
python3 tools/x87_audit.py local/original-th06/東方紅魔郷.exe \
  --mapping repos/th06/config/mapping.csv \
  --implemented repos/th06/config/implemented.csv \
  --summary
```

The tool invokes GNU `objdump`, records its version, emits only derived
metadata, and never copies executable bytes. The synthetic unit test requires
no proprietary input:

```sh
python3 tests/test_x87_audit.py
```

## Static census

GNU `objdump` 2.38 linearly decoded 133,078 instruction lines. Of these,
10,100 have x87 mnemonics; 9,522 fall in a mapped function range and 578 do not.
The complete-image x87 counts include:

| Category | Static instructions |
| --- | ---: |
| control/environment save, load, or clear | 77 |
| transcendental or square-root | 65 |
| rounding or float-to-integer conversion | 92 |
| x87 comparisons | 350 |
| floating or integer stores | 3,016 |

The complete image contains 2,689 `fld`, 2,859 `fstp`, 30 `fsincos`, 17
`frndint`, 74 `fistp`, and one `fisttp`. The store census includes 2,320
`fstp` stores to a DWORD, 167 to a QWORD, and 137 to a TBYTE. These are static
sites, not execution frequencies.

There are also 356 instruction lines with an XMM operand. None lie in a mapped
`th06::` function: 332 are in the statically linked Pentium-4 `pow` routine, 23
are in one CRT helper called by D3DX rasterization, and one detects OS XMM-state
support. This does not prove those routines unreachable. It makes SSE/D3DX
reachability an explicit slicing obligation rather than silently treating the
whole executable as x87-only.

### Mapped game functions

The mapping attributes x87 instructions to 159 `th06::` functions, all marked
implemented by the pinned reconstruction metadata. Together they contain:

| Property | Static count |
| --- | ---: |
| x87 instructions | 5,980 |
| direct x87 control/environment instructions | 0 |
| `fsincos` instructions | 26 |
| `frndint` instructions | 10 |
| `fcomp` instructions | 244 |
| `fcomp` DWORD/QWORD memory operands | 236 / 8 |
| x87 stores | 1,793 |
| stores to binary32-width DWORDs | 1,713 |
| stores to binary64-width QWORDs | 80 |

The largest mapped bodies demonstrate why presentation slicing and arithmetic
modeling cannot be decided independently:

| Function | x87 | `fsincos` | stores |
| --- | ---: | ---: | ---: |
| `BulletManager::OnUpdate` | 393 | 7 | 119 |
| `EclManager::RunEcl` | 276 | 1 | 71 |
| `Gui::DrawGameScene` | 242 | 0 | 108 |
| `AnmManager::ExecuteScript` | 189 | 0 | 45 |
| `Player::HandlePlayerInputs` | 170 | 0 | 41 |
| `BulletManager::SpawnSingleBullet` | 166 | 3 | 43 |
| `Stage::RenderObjects` | 165 | 0 | 36 |
| `Player::CalcLaserHitbox` | 114 | 0 | 30 |
| `Player::CalcDamageToEnemy` | 107 | 0 | 24 |
| `Player::UpdatePlayerBullets` | 102 | 0 | 25 |

The 26 mapped transcendental sites are all `fsincos`; they occur in ECL,
stage-specific enemy instructions, bullet spawn/update/despawn, item update,
and two draw routines. The address-level list is emitted by `--summary`.

All 244 mapped comparison sites use `fcomp`; every site is immediately followed
by `fnstsw ax`, one of six observed `and`/`test` masks, and one of `je`, `jne`,
`jp`, or `jnp`. The audit emits all addresses and the eleven complete consumer
signatures. These sequences, rather than a guessed source-level relation, are
the branch-semantics extraction obligations.

| Status consumer after `fnstsw ax` | Sites |
| --- | ---: |
| `and eax,0x100; je` / `jne` | 1 / 32 |
| `and eax,0x4100; je` / `jne` | 18 / 22 |
| `test ah,0x1; jne` | 13 |
| `test ah,0x41; jne` / `jp` | 7 / 38 |
| `test ah,0x44; jnp` / `jp` | 11 / 18 |
| `test ah,0x5; jnp` / `jp` | 16 / 68 |

The masks observe different unordered behavior. For example,
`test ah,0x5; jp` branches for greater, equal, and unordered, while
`test ah,0x5; jnp` branches only for less. `X87Compare.lean` evaluates every
observed signature over the four x87 relations so that later IR extraction can
preserve the machine branch exactly.

### Arithmetic hidden behind calls

Counting only instructions inside a mapped game body misses statically linked
helpers. The audit finds 163 direct calls from `th06::` functions to 18 mapped
x87-containing helpers or wrappers:

| Helper | Direct sites | Calling game functions |
| --- | ---: | ---: |
| `__ftol2` | 77 | 28 |
| `sin` | 16 | 13 |
| `cos` | 16 | 13 |
| `sqrt` | 11 | 6 |
| `D3DXVec3Project` | 10 | 1 |
| `atan2` | 7 | 6 |
| `_fabs` | 5 | 4 |
| `tan` | 3 | 3 |
| other D3DX vector/matrix helpers | 18 | 15 caller/helper pairs |

For example, `__ftol2` uses `fistp` plus an integer correction sequence, while
two D3DX `F2IBegin`/`F2IEnd` pairs temporarily set the x87 rounding-control
bits to toward-zero and then restore the prior word. These are semantic helper
ABIs, not interchangeable calls to a host conversion routine.

At all 77 mapped `__ftol2` calls, the preceding instruction is x87: 60 `fld`,
seven `fmul`, four `fdiv`, two `fadd`, two `fsubp`, and two `fsubr`. A bounded
straight-line result-use scan observes EAX at all 77 sites and EDX at none; one
site was initially reported as AL-only. A bit-mask re-audit corrects that count
to two AL-only sites and 75 full-EAX sites. Because the scan stops at a branch
or subsequent call and leaves EDX live at 42 stopping points, it supports only
a candidate low-32-bit projection; it proves neither complete result deadness
nor that every reachable conversion is in range.

## Control-word evidence

The bytes at virtual address `0x00470308` (file offset `0x00070308`) are
`7f 02`, the little-endian x87 control word `0x027f`. The CRT `sin` body loads
this word at `0x0045bd0c` when the current word differs; `cos` does the same at
`0x0045bdbc`. Square root error handling preserves the current precision bits
while restoring masked exceptions and round-to-nearest. No mapped `th06::`
function directly changes the control word.

The raw `0x027f` profile means:

- all six x87 exceptions are masked;
- precision control is the 53-bit significand mode; and
- rounding control is round-to-nearest-even.

The bit decoding is machine-checked in
[`formal/ZkTH06/X87Profile.lean`](../formal/ZkTH06/X87Profile.lean). Intel's
[floating-point reference sheet](https://www.intel.com/content/www/us/en/developer/articles/technical/floating-point-reference-sheet-for-intel-architecture.html)
documents the raw control-word fields, while Microsoft's
[`_control87` documentation](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/control87-controlfp-control87-2)
explains the precision, rounding, and exception controls.

This static evidence is deliberately not promoted into a startup theorem. No
game-body `fldcw` establishes `0x027f` before the first mapped transition, and
the value at an executable address does not prove the loader's ambient state.
The original exporter must record the entry/gameplay control word. The exact
runner and future guest must reject any initial profile other than the one
named by the statement.

Precision control also does not make every live x87 value an IEEE binary64
value. x87 registers retain the double-extended exponent range, selected
operations use the control-word significand precision, and explicit stores
round to their destination width. The pinned reconstruction uses MSVC 7 flags
including `/Op`; nevertheless, the actual instruction and store boundaries,
not a modern compiler's interpretation of the C++ expression, are binding
evidence.

## Arithmetic-boundary differential oracle

An executable experiment tests whether Berkeley SoftFloat Release 3e is a
plausible independent oracle for the reached arithmetic subset. The source is
not vendored. [`tools/run_softfloat_probe.py`](../tools/run_softfloat_probe.py)
exports exact commit
`f74b1e48110ac3a27dd49b787d164e55e42d81d1` from an ignored checkout, verifies
selected file hashes, compiles the 37 required translation units with the
`8086` specialization in a temporary directory, and runs
[`arithmetic/softfloat_probe.c`](../arithmetic/softfloat_probe.c).

For `add`, `sub`, `mul`, `div`, and `sqrt`, the probe compares raw extended
result bits under control word `0x027f` with SoftFloat configured for
round-to-nearest-even and `extF80_roundingPrecision = 64`. SoftFloat documents
this setting as precision equivalent to `float64_t`: a 53-bit significand while
retaining the extended exponent range. The probe additionally compares `fstp`
to binary32/binary64, `frndint`, and signed 32/64-bit `fistp` under both
`0x027f` and the D3DX helper's toward-zero profile `0x0e7f`. Both profile
decodings and their SoftFloat configuration mappings are checked, without an
arithmetic theorem, in `X87Profile.lean`.

The same probe mirrors the 244 mapped comparison forms with `fcomp m32fp` and
`fcomp m64fp`. It checks C0, C1, C2, and C3 plus exception bits, including
fixed infinity, quiet-NaN, signaling-NaN, signed-zero, and invalid-versus-
denormal priority cases. `X87Compare.lean` checks the documented relation
encoding and truth tables of all eleven status-mask/branch signatures found by
the audit. It does not prove that the binary implements the Lean definition.

The comparison now covers x87 exception bits 0--5 as well as results.
SoftFloat's invalid, divide-by-zero, overflow, underflow, and inexact flags map
directly. Its API has no x87 denormal-operand flag, so that bit is supplied by
an opcode-specific predicate from the instruction reference. This distinction
was experimentally necessary: a naive rule that marked every operation with a
subnormal input disagreed on subnormal-dividend divided by zero, where the
higher-priority zero-divide condition suppresses the arithmetic instruction's
denormal flag. `fistp` and `fstp` also do not define that exception, while
`frndint` does. These rules follow Intel's
[Volume 2A instruction pages](https://www.intel.com/content/www/us/en/content-details/850971/intel-64-and-ia-32-architectures-software-developer-s-manual-volume-2a-instruction-set-reference-a-l.html)
and are cross-referenced against AMD's
[x87 instruction manual](https://docs.amd.com/v/u/en-US/26569_3.16); they are
not inferred from SoftFloat.
[`formal/ZkTH06/X87Exceptions.lean`](../formal/ZkTH06/X87Exceptions.lean)
machine-checks the finite-class counterexamples and boundary predicate, while
explicitly making no hardware-correctness claim.

Two deterministic input families cover finite binary32-derived operands and
canonical finite extended operands whose low eleven significand bits are zero,
as expected after a 53-bit-precision operation. Boundary-heavy sampling spans
the extended exponent range and signed integer limits. On the initial AMD EPYC
9654 host with GCC 11.4.0, one million pseudorandom cases per operation,
profile, and family plus fixed boundary cases produced:

| Family | binary32-derived tuples | PC53 extended tuples | Mismatches |
| --- | ---: | ---: | ---: |
| five basic operations | 5,000,798 | 5,001,314 | 0 |
| five boundaries, two RC profiles | 10,000,140 | 10,000,330 | 0 |

All six exception bits occurred in the basic campaign: 1,001,228 invalid,
88,466 denormal-operand, 56 divide-by-zero, 255,746 overflow, 265,276
underflow, and 7,547,221 inexact observations. Counts overlap when multiple
bits are set. A further 2,000,110 DWORD-memory and 2,000,110 QWORD-memory
comparison tuples matched, with 76 invalid and 29,682 denormal-operand
observations. Across all campaigns, 34,002,802 result/condition/exception
tuples matched.

This is host-specific counterexample search, not a proof that either
implementation is correct. It does not cover TOP/tag state, stack faults,
arbitrary NaN payloads or noncanonical ext80 encodings, `fld m32fp` denormal
signaling, remainder, `fisttp`, transcendental instructions, or address
extraction. SoftFloat is therefore a candidate
executable specification for a subset, not the soundness argument. Full
commands and the dependency/license boundary are in
[`arithmetic/README.md`](../arithmetic/README.md).

## Extracted `__ftol2` experiment

The audited helper occupies 117 bytes at `0x0045ba78`, with body SHA-256
`5333b186c02836974c6f792303aeb2c00d856316b93ccbbe65f51def6ae661b4`.
The local runner resolves that address through the verified PE section table,
checks the body hash, and embeds it only in a temporary freestanding i386
harness. No original byte is tracked or retained. The harness supplies one
ext80 stack operand, executes the exact helper at control word `0x027f`, and
returns EDX:EAX plus the status word.

An independent integer decoder interprets canonical finite ext80 inputs as
exact dyadic rationals. Across 1,000,014 fixed and deterministic PC53 samples
in the signed-i64 domain, the complete EDX:EAX result always equaled truncation
toward zero and the helper always returned with an empty x87 stack. This tests
the body and ABI rather than merely its inner `fistp`. `X87Ftol2.lean` checks
the nearest-integer correction table and EDX:EAX split/join identities, but
does not connect raw encodings, executable bytes, or reachable inputs to those
definitions.

A second focused campaign tests the narrower ECL-variable observation. It
combines exact fractional boundaries around `-10025..-10001`, dense
deterministic PC53 samples, infinities, quiet/signaling NaNs, very large finite
values, a pseudo-denormal, and an unnormal. All 1,000,154 exact-helper outputs
agreed with the independent 25-way classifier; 3,084 selected a variable and
nine set invalid. Together both campaigns execute the helper 2,000,168 times.

Exceptional/out-of-range full results remain outside the first result, and the
classifier campaign is finite testing rather than a theorem. The correct
simplification premise is now site-specific. General EAX consumers require
their actual reachable result range unless another observation quotient is
proved; `GetVarFloat` needs only exact agreement on the 25 sentinel outcomes.
The helper remains retained until those refinement and code-binding
obligations are established.

## Source candidates and ECL dispatch quotient

A derived source ledger aligns all 77 addresses with expression candidates in
the pinned authoritative source. It labels 68 presentation/audio conversions
as `omit-after-noninterference` candidates and nine as retain candidates: the
single ECL variable conversion and eight point-item score conversions. These
labels are manual disassembly/source alignments with checked Git line anchors,
not compiler correspondence or slicing proofs. All proof statuses remain
`unproved`.

For `EnemyEclInstr::GetVarFloat` at `0x0040b38b`, a second hash-bound artifact
checks 17 critical instruction signatures and derives the 25 unique targets in
the jump table at `0x0040b31c`. The machine adds 10025 modulo $2^{32}$ and
accepts unsigned indices at most 24. A Lean bit-vector theorem checks that this
is exactly the signed interval `-10025..-10001`; another abstract theorem shows
that the precise integer is irrelevant outside that interval because the
original float pointer is returned. This replaces a global range target for
that call with the narrower helper-to-classifier refinement target.

The static artifact is not verified decoding, does not yet associate each
target body with its modeled ECL value, and does not bind either reference
function to a guest. The eight score calls still need a reachable finite and
signed-32-bit bound for collected item `y`. Reproduction commands, artifact
digests, and the per-site discharge discipline are in
[`arithmetic/README.md`](../arithmetic/README.md) and
[`arithmetic-obligations.md`](arithmetic-obligations.md).

## Transcendentals are a scope decision

The `fsin`, `fcos`, `fsincos`, and `fptan` instructions are approximations, not
abstract correctly-rounded real functions. Intel documents both their limited
argument reduction and their use of an internal approximation of pi in
[its x87 transcendental note](https://www.intel.com/content/www/us/en/developer/articles/technical/the-difference-between-x87-instructions-and-mathematical-functions.html).
Implementations have evolved across processor generations. Therefore
"bit-exact to the executable" is incomplete unless it also names the target
execution profile for those instructions.

There are three honest possible claims:

1. pin a physical CPU/microarchitecture profile and implement that profile's
   observed instruction results;
2. pin a deterministic emulator arithmetic profile, while clearly claiming
   equivalence to that profile rather than every physical v1.02h execution; or
3. implement a verified mathematical reducer and prove that its stored result
   equals the target instruction at every reachable call.

The third is the strongest portable result and the hardest. Until one of these
is selected and validated, host `std::sin`, `std::cos`, and `std::sqrt` remain
diagnostic compatibility code, not authoritative proof semantics.

## Proof-oriented arithmetic architecture

The fidelity lane will use an address-indexed arithmetic IR extracted from the
pinned binary/mapping pair. Its first public index is the hash-bound
[`arithmetic/obligations-v1.json`](../arithmetic/obligations-v1.json) ledger: it
names all 244 comparison and 77 `__ftol2` addresses, points their observations
to the current Lean contracts, and leaves every slice/range status explicitly
open. It contains no executable bytes or full disassembly operands. A later IR
operation record must additionally name x87 stack inputs, control word, opcode,
destination width, and next use/store boundary. Helper calls such as `__ftol2`
and D3DX conversions remain explicit IR operations. The public statement
commits to the executable digest, ledger/profile version, initial control word,
and transcendental model identifier.

This layout separates four arguments:

1. **Extraction:** each retained original basic block is translated to the IR
   operation sequence associated with its pinned address;
2. **Arithmetic semantics:** an integer/bit-vector implementation realizes the
   selected x87 and any retained SSE operations exactly;
3. **Slicing:** omitted draw/audio/helper paths cannot change the next projected
   gameplay state, including shared RNG and future-live shadow state; and
4. **Guest refinement:** the zkVM kernel commutes with the extracted canonical
   transition and preserves the acceptance predicate.

This is more proof-friendly than rewriting expressions first and later trying
to recover where MSVC kept or spilled an intermediate. The reconstructed C++
remains essential for names, ownership, invariants, and differential diagnosis;
the pinned binary addresses bind the arithmetic details that the source
language leaves implementation-dependent.

The optimization lane may replace a field with fixed-point or integer phase
arithmetic only after a theorem covers its reachable range, overflow behavior,
rounding, comparisons, collision decisions, RNG schedule, and terminal
observation. An error bound is insufficient when two nearby results can choose
different branches. If exact refinement cannot be proved, that implementation
must be published as a distinct integer-kernel game rather than v1.02h
equivalence.

## Open obligations and next experiments

1. Record x87 control word and CPU identity at exporter entry and at the first
   gameplay tick; reject changes outside audited helper save/restore regions.
2. Instrument the 26 inline `fsincos` sites and 163 direct helper-call sites to
   collect dynamic call counts, raw inputs, raw outputs, and ranges over the
   replay corpus.
3. Add field-level snapshots so the first arithmetic divergence identifies the
   owning field and original operation site.
4. Discharge the address ledger: translation-validate retained comparison and
   conversion blocks, prove noninterference for omitted ones, establish
   control-flow-complete result use, prove the ECL helper/classifier refinement
   and the point-item `y` range invariant, and extend the oracle through
   `fisttp`, `fld` denormal signaling, remainder, and exceptional inputs where
   relevant.
5. Prove draw/D3DX noninterference one callback at a time. Only then may their
   x87 and XMM sites leave the arithmetic kernel.
6. State and prove the chosen transcendental execution profile; corpus equality
   is counterexample search, not a universal proof.
7. Benchmark exact and refined lanes separately. Proof cost never licenses a
   silent weakening of arithmetic semantics.

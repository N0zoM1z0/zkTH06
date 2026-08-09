# Address-level arithmetic obligations

[`arithmetic/obligations-v1.json`](../arithmetic/obligations-v1.json) is the
machine-readable bridge between the pinned retail image, the static x87 audit,
and the small Lean arithmetic models. It records 244 mapped comparison sites
and 77 mapped `__ftol2` calls without redistributing executable bytes or full
disassembly operands.

The ledger is an index of claims that still need proofs. It is not itself a
binary-decoding, reachability, slicing, or refinement theorem. In particular,
every site deliberately starts with `slice_disposition: "unclassified"`; every
conversion site starts with `reachable_signed_i32_range: "unproved"`.

## Identity and regeneration

Version 1 is bound to:

| Input | SHA-256 |
| --- | --- |
| Japanese v1.02h executable | `9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245` |
| authoritative `mapping.csv` | `0f20300d5b107b36c933a7f7dc448407ee5f01c5cd7faad132d406c023163191` |
| authoritative `implemented.csv` | `07b448de3503a285f3464f618c7c384607050c0fff81e0642aa13968fcb61311` |

The tracked artifact digest is
`1c4c128284bf5ab4aa36e636cd5ed15f0300e5295e7fb29f12c0cb2f897f65af`.
It is SHA-256 over canonical JSON after removing the `artifact_sha256` field.
The document also records hashes of both generator scripts and the disassembler
identity, so a regenerated artifact exposes tool drift.

With a legitimate local retail image and the pinned authoritative checkout,
regenerate and compare the ledger with:

```sh
python3 tools/arithmetic_obligations.py \
  local/original-th06/東方紅魔郷.exe \
  --mapping repos/th06/config/mapping.csv \
  --implemented repos/th06/config/implemented.csv \
  --check arithmetic/obligations-v1.json
```

Use `--output arithmetic/obligations-v1.json` only when intentionally updating
the schema or pinned evidence. Public CI runs
`tests/test_arithmetic_obligations.py`: it verifies the artifact digest, tool
hashes, address uniqueness, distributions, conservative status fields, and
absence of disassembly operand strings. CI does not fetch an external checkout
or require proprietary input.

## Comparison obligations

Each comparison record contains the original address, mapped function and
offset, memory width, immediate status consumer signature, and the identifier
of one obligation class. A top-level contract table maps all eleven signatures
to the corresponding Lean truth-table theorem. The current distribution is
236 `fcomp m32fp` and eight `fcomp m64fp` sites.

For each retained site, the eventual soundness argument must establish all of:

1. the pinned bytes and local successors decode to the recorded instruction
   and status consumer;
2. the reference x87 stack, memory operand, control word, and exception state
   refine the arithmetic model;
3. the zk implementation produces the same relation, C-code observation, and
   exception priority; and
4. the modeled branch and its successors preserve the projected transition.

For an omitted site, item 4 becomes a noninterference proof for every projected
successor state; a rendering-looking function name is not evidence enough.

## `__ftol2` obligations

Each helper record contains its call address, mapped function/offset, preceding
x87 mnemonic, and a bounded explicit-register use result. The improved scan
tracks bit masks rather than a single Boolean:

| First recorded result projection | Sites |
| --- | ---: |
| complete EAX (`0xffffffff`) | 75 |
| AL only (`0x000000ff`) | 2 |
| any EDX bits | 0 |

The two AL-only calls are `th06::Stage::OnUpdate` at `0x00403f4c` and
`th06::BulletManager::AddedCallback` at `0x00416fbc`. This corrects the earlier
coarser report that described only one AL consumer.

The scan stops at a control-flow boundary for 15 calls, at a subsequent call
for 34, and after both tracked registers are syntactically resolved for 28.
EDX remains live at 42 stopping points. Therefore “zero observed EDX sites” is
only a bounded straight-line fact; it is explicitly not a whole-function or
interprocedural dead-result proof.

Before a retained helper call can become a smaller signed conversion in the
zk kernel, the project still needs:

1. control-flow-complete EDX:EAX use analysis;
2. a proof that every reachable input is canonical finite and truncates into
   signed 32 bits;
3. a raw-ext80 and x87-stack refinement for the 117-byte helper body; and
4. a binding from that model to the guest conversion gadget.

The exact helper remains the executable oracle until those premises close.

## Discharge discipline

A future ledger revision should replace `unclassified` only with a structured
record that names either:

- a retained transition/gadget and its code-binding and refinement theorem; or
- an omitted path and its projection noninterference theorem.

Empirical replay coverage or differential arithmetic samples may accompany a
record as counterexample-search evidence, but cannot change its proof status.
The final whole-run theorem must quantify over a ledger revision/digest and
require every site reachable under the claimed game mode to be discharged.

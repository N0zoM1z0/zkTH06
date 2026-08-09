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

## Source/sink classification candidates

[`arithmetic/ftol2-source-candidates-v1.json`](../arithmetic/ftol2-source-candidates-v1.json)
adds a conservative candidate annotation for every one of the 77 base-ledger
calls. It is bound to authoritative source revision
`cc475a0bc3fef38683b0f02224c87ddba0a021d9`, hashes each of the 16 referenced
source files, and checks every recorded line anchor against the pinned Git
blob. The artifact digest is
`2885d3ed814784f4446a8f977646b3f1fc2edbdd058285ec37eb77d089a16466`.

The alignment combines mapped function ownership, local disassembly dataflow,
source order, and exact source anchors. It is explicitly marked
`manual-disassembly-source-alignment-unproved`: it is neither debug-line
evidence nor a compiler-correctness theorem. Its current queue is:

| Candidate disposition | Calls | Meaning |
| --- | ---: | --- |
| `omit-after-noninterference` | 68 | presentation/audio sink; still retained until transitive noninterference is proved |
| `retain` | 9 | one ECL variable dispatch and eight point-item score conversions |

Thus the artifact prioritizes proof work but discharges no base-ledger entry.
In particular, labels such as `d3d-viewport` or `audio-volume` are semantic
sink hypotheses, not permission to remove those paths.

## Observation-specific ECL narrowing

The retained call at `0x0040b38b` is narrower than a general integer cast.
[`arithmetic/ecl-var-dispatch-v1.json`](../arithmetic/ecl-var-dispatch-v1.json)
binds the pinned image, mapping, and base ledger; checks 17 instruction
signatures in `EnemyEclInstr::GetVar` and `GetVarFloat`; and extracts the
25-entry jump table at `0x0040b31c`. The wrapping `add eax, 10025` followed by
an unsigned comparison with 24 recognizes precisely the signed 32-bit labels
`-10025..-10001`. All other conversion outputs cause `GetVar` to return its
input integer pointer, after which `GetVarFloat` returns the original float
pointer. The artifact digest is
`4f30ab443aa0a557ed7d39c2389a8be329601eba956aed073f05bad51b46e4cc`.

`ZkTH06.EclVarId.machine_classifier_matches_signed_interval` checks the
32-bit wrapping-add/unsigned-compare identity with `bv_decide`.
`nonvariable_integer_value_is_irrelevant` proves in the abstract resolver that
any two non-label results make the same choice. Together these facts change the
desired refinement for this call: prove that the exact helper and guest agree
on the 25-way classifier, rather than first proving that every reachable input
has an arbitrary signed-32-bit conversion result.

This is a reduction in proof surface, not a completed proof. Static decoding is
still performed by unverified `objdump`; table targets are not yet bound to the
modeled variable values; the helper/classifier agreement has only finite
boundary and exceptional-input testing; and no guest resolver is connected to
the Lean model. The other eight retained calls use a second observation quotient
that handles exceptional item coordinates without assuming them unreachable.

## Helper masked-invalid quotient

[`arithmetic/ftol2-helper-v1.json`](../arithmetic/ftol2-helper-v1.json) checks
all 37 instruction signatures in the pinned 117-byte helper. Under the
architectural premise that masked-invalid `fistp m64int` stores integer-
indefinite `0x8000000000000000`, the checked path loads EAX zero and EDX
`0x80000000`, takes the zero-low-half branch, bypasses correction, pops both x87
values, and returns unchanged. `ZkTH06.X87Ftol2` proves the constant split and
low-EAX projection. The artifact digest is
`46c87767f9d864ebbb2eca60d698fdaa6f355674c51d231f510e369f77427153`.

This is still conditional evidence. The static decode, masked-invalid x87
semantics, entry stack/tags/control word, branch refinement, caller connection,
and guest implementation all remain open. The exact-byte probe found the same
integer-indefinite result in nine exceptional cases, but finite testing is not
the missing universal theorem.

## Point-item score contract and the NaN trap

[`arithmetic/item-score-v1.json`](../arithmetic/item-score-v1.json) binds all
eight remaining retain candidates to the four score profiles in the pinned
`ItemManager::OnUpdate` body. It checks 77 exact instruction signatures, the
five-entry Easy/Normal/Hard/Lunatic/Extra table, two loads from the same
binary32 `Item.currentPosition.y` field per profile, both helper calls, signed
comparison with 128, profile constants, 32-bit penalty arithmetic, and the
final addition to gameplay score. Its artifact digest is
`25319fc8d8a188103111b64426844dfb0c4399dfc7f6849ac1f48bf45dc8d138`.

The total range argument has four separate bindings:

1. the player center/grab box is finite and its center stays in `16..432`;
2. the AABB test uses ordered x87 comparisons, player radius 12, and item
   half-size 8;
3. finite binary32 values enter the exact rational/truncation model, infinities
   are separated, and NaN is unordered; and
4. the exact helper returns truncation on the bounded finite branch and low EAX
   zero on masked invalid.

Item finiteness cannot be inferred from successful collision. The source test
rejects separated boxes using ordered comparisons; a NaN coordinate makes
those comparisons false and can therefore fall through to collision success.
The proof therefore handles NaN rather than assuming it away. With a finite
player box, positive and negative infinity are separated. NaN can collide, but
its modeled integer-indefinite result has EAX zero and selects the bounded top-
score branch.

For the finite branch, player center in `16..432`, player radius 12, and item
half-size 8 imply ordered overlap within a narrow interval.
`ZkTH06.ItemPointScore.finite_collection_bounds_item_y` derives the exact
rational item interval `-4..452`, and truncation toward zero preserves it.
`collected_score_range_without_item_finiteness` then covers the finite,
infinity, and NaN classes and proves a result interval
`27600..300000`, signed-i32 safety, and a maximum lower-branch position penalty
of 129600. Given a pre-update score in `0..999999999`, it also proves that one
item award cannot wrap u32. Reachable difficulty must separately stay in the
decoded `0..4` interval; the invalid binary path skips profile assignment.
These are checked mathematical consequences of the stated total model, not
binary/x87/caller/guest correspondence theorems.

[`arithmetic/item-score-corpus-v1.json`](../arithmetic/item-score-corpus-v1.json)
records a separate Linux reconstruction experiment. GDB breakpoints captured
the raw binary32 field at all four source score calls: 2,081 collections across
the four pinned replays were finite, none left `-4..452`, the measured range was
approximately `11.879809..442.976013`, and truncated values ranged from 11 to
442. Of these, 1,413 took the top branch and 668 the position branch. The report
is sealed and binds its probe, debug runner, source, replay, and data-manifest
hashes. It is counterexample search only and does not transfer reconstruction
observations to the retail executable. The total theorem no longer needs its
observed absence of exceptional item values as a premise.

## Discharge discipline

A future ledger revision should replace `unclassified` only with a structured
record that names either:

- a retained transition/gadget and its code-binding and refinement theorem; or
- an omitted path and its projection noninterference theorem.

Empirical replay coverage or differential arithmetic samples may accompany a
record as counterexample-search evidence, but cannot change its proof status.
The final whole-run theorem must quantify over a ledger revision/digest and
require every site reachable under the claimed game mode to be discharged.

# State projection soundness audit

Last updated: 2026-08-10

This document tracks whether the state selected by the canonical trace is
closed under the pinned reference transition. Revision 0.2 is a diagnostic
projection, not yet a quotient state or a proved gameplay kernel.

## Admission rule

A reference field may be absent from the eventual kernel only when one of the
following facts is established for every reachable state in the claimed game
and data revision:

1. it is immutable and derived from committed program or data bytes;
2. it is overwritten on every path before any later read;
3. it cannot affect the next projected state, including control flow, shared
   RNG consumption, allocation order, collision geometry, or the terminal
   predicate; or
4. it is a deterministic function of fields already in the projection.

We call a value **future-live** when a later reference step can read it before
an unconditional overwrite and thereby change the projected transition. The
target noninterference lemma is therefore stronger than “the field is not
rendered” or “the sampled replays still finish.”

## Finding 1: raw object memory is not canonical state

Stage ANM VMs are allocated with `malloc`, while `AnmVm::Initialize` assigns
only the members enabled by the current animation mode. The first attempt to
hash every named member produced a Stage mismatch at record zero in two
otherwise identical 2,000-tick executions. RNG, Player, and all other subsystem
digests still agreed. The mismatch came from disabled interpolation members
whose values were never initialized.

Revision 0.2 now encodes ANM state by future-read guards:

- scale interpolation origins and timer only when `scaleInterpEndTime > 0`;
- alpha endpoints and timer only when `alphaInterpEndTime > 0`;
- position endpoints and timer only when `posInterpEndTime != 0`;
- `baseSpriteIndex` only at an owner that reads it outside the ANM interpreter;
- active sprite pointers as stable sprite-table indices, never addresses; and
- script cursors as offsets relative to their script base.

After this change, two 2,000-tick traces and two complete 85,759-tick traces
were byte-identical. This is evidence that the representation is deterministic;
it is not yet a proof that every future-live ANM member is present.

## Finding 2: inactive slots need reuse proofs

Stable allocation slots remain semantically relevant even while inactive if
their residual values survive reuse. The current audit is:

| Pool | Reference reuse behavior | Revision 0.2 treatment | Obligation |
| --- | --- | --- | --- |
| Enemies | `SpawnEnemy` copies the initialized `enemyTemplate` before ECL runs. | Active slots and stable references are hashed. | Prove the template is immutable after initialization and covers every field read by ECL. |
| Enemy bullets | Ordinary retirement reaches `memset(..., 0, sizeof(Bullet))`; spawning then assigns mode-specific state. | Nonzero-state slots are hashed in slot order. | Audit every path to state zero and every flag-specific spawn/read pair. |
| Lasers | Spawn assigns both VMs and every scalar used by the update loop. | Active slots are hashed in slot order. | Prove ANM guarded-state initialization and all retirement paths. |
| Items | Spawn assigns position, velocity, type, state, timer, and sprite; `targetPosition` is read only in state 2, where spawn assigns it. | Active slots and allocator cursor are hashed. | Prove the state partition and account for any RNG-consuming item ANM opcode. |
| Player bullets | Character/shot callbacks populate a reused slot and start its ANM program. | Active slots, gameplay fields, and ANM state are hashed. A local Reimu-A ranks 1--3 transition now carries all four non-laser dormant fields and matches 1,590 retail/reference callback projections. | Link calls through update/collision/ANM reclamation; prove fixed trig helper results; extend ranks 4--5 and the other shot routes. |
| Effects | Retirement clears only `inUseFlag`; spawn does not clear all motion fields. Spell-card effects can reuse `unk_15c` and `angleRelated`, and callback-specific fields have different initialization rules. | Only active slots and allocator cursor are hashed. | **Open counterexample to closure:** include a dormant reuse shadow, canonicalize allocation with a proved refinement, or strengthen the reachable-state invariant. |

The Effects row is enough to reject a claim that revision 0.2 is a Markov state
projection. Two full reference states may agree on its active-only digest yet
advance differently after the same future effect allocation.

## Finding 3: presentation code can perturb gameplay RNG

The global RNG is shared. `AnmOpcode_SetRandomSprite` consumes it, as do active
screen-shake callbacks. Consequently an animation can be gameplay-relevant even
when its pixels are outside the acceptance predicate. Revision 0.2 includes ANM
control state owned by Player, active player bullets, active enemy bullets,
lasers, items, enemies, Stage, GUI/message, and effects.

Dynamic `ScreenEffect` chain elements are not yet represented. Their callback
identity, timer, length, and shake parameters must either enter the projection
or be removed behind a noninterference/refinement theorem. The same audit must
cover every skipped draw callback that mutates later-read state.

## Current coverage and open boundary

| Subsystem | Included examples | Known open boundary |
| --- | --- | --- |
| Global | frame/state counters, input masks, score/resources/rank, region geometry, time-stop state | dynamic calc-chain jobs, additional Supervisor/GameManager control fields |
| RNG | complete seed and generation count | call-site attribution for first-divergence diagnosis |
| Player | motion/collision/bomb state, counters, active ANM control | callback identity is presently treated as configuration-derived; inactive bullet overwrite proof |
| Enemy/ECL | active slots, contexts/stacks, movement, shooters, boss/spell state, stable laser/effect references | proof that inactive slots are template-overwritten; exhaustive callback identity table |
| Bullets/lasers/items | allocator state, stable active slots, collision/motion/timers, relevant ANM control | exhaustive reuse and script-opcode audit |
| Stage | script/interpolation state, object flags, quad VMs, spell background | static-data binding and exact draw/calc dependency split |
| GUI/message | message cursor/timers, stage completion state, owned VMs | full menu/retry state and skipped-draw mutations |
| Effects | active slots, callbacks, motion, ANM state | dormant future-live residue; this currently prevents projection closure |

All serialized floats retain their raw binary32 bits. This preserves evidence
of arithmetic differences but does not define the x87 intermediate-precision
semantics needed by the authoritative transition.

## Lean obligation queue

The first reusable lemmas should be small owner-local statements rather than a
monolithic game proof:

```text
enemy_spawn_overwrites_inactive
enemy_bullet_zero_is_canonical
laser_spawn_overwrites_future_live
item_state2_initializes_target
player_bullet_callback_initializes
anm_disabled_interpolation_irrelevant
effect_reuse_shadow_sufficient
screen_effect_projection_noninterference
```

The first checked artifact is
[`../formal/ZkTH06/EffectReuse.lean`](../formal/ZkTH06/EffectReuse.lean). It
constructs the active-only counterexample and proves the commuting allocation
step for a narrow spell-orbit model retaining dormant radius and angle. The
remaining effect fields and callbacks are still open.

Each lemma needs a source/data binding and a reachable-state precondition. Once
these hold, they can discharge cases of the global quotient obligation recorded
in [`../formal/README.md`](../formal/README.md).

## Evidence boundary

Cryptographic digest equality means equality of the bytes selected by this
serializer, under the collision-resistance assumption for SHA-256. Repeated
trace equality is a counterexample search and regression check. It proves
neither that omitted fields are irrelevant nor that the Linux transition
matches the shipped 32-bit executable.

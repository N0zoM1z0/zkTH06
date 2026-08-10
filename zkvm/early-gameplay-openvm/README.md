# OpenVM early-gameplay adapter

This OpenVM v2.0.1 guest receives only replay input masks after the fixed
gameplay-frame-1 anchor. It derives the enclosing Reimu-A Player/bullet state
and the first five Stage-1 `Sub0` enemies through the first real hit at frame
208. The guest executes timeline spawns, movement, ECL time/angle updates,
AABB damage, the slot-2 collision animation transition, enemy death, target
selection, and score.

The 207-transition private payload is 438 bytes. No per-frame Player, bullet,
Enemy, ECL, collision, life, or score value is supplied as a witness. The
public statement commits the payload, every retained Enemy-state projection,
200 damage calls, the unique collision, and the frame-208 result.

Build an input and meter the full profile with:

```sh
python3 tools/build_early_gameplay_openvm_input.py \
  evidence/early-gameplay-002677-208-v1.bin \
  local/openvm/early-gameplay-207.json \
  --report local/openvm/early-gameplay-207-report.json

cargo openvm build \
  --manifest-path zkvm/early-gameplay-openvm/Cargo.toml --locked
cargo openvm run \
  --manifest-path zkvm/early-gameplay-openvm/Cargo.toml \
  --input local/openvm/early-gameplay-207.json --mode meter --locked
```

The tracked application proof can be checked without the private replay input
or a proving key:

```sh
cargo openvm verify app \
  --manifest-path zkvm/early-gameplay-openvm/Cargo.toml \
  --proof evidence/openvm-early-gameplay-207-v1.app.proof \
  --app-vk evidence/openvm-early-gameplay-v1.app.vk \
  --app-commit evidence/openvm-early-gameplay-v1.app-commit.json
```

Its 32 authenticated public bytes are
`0909a289f39eb51f601649161ff98ca479a114dbc9b449a0939202c8b3f73f40`.
The evidence manifest binds this value, the executable commitment, all source
inputs, and the finite claim boundary.

This proof boundary is finite and route-specific. In particular, the fixed
40-entry curved-axis lookup is constrained by derived ECL time and agrees with
both execution oracles, but its refinement to the pinned x87 `fsincos` path is
still an explicit proof obligation.

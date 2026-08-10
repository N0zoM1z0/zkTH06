# OpenVM linked Player/bullet lifecycle adapter

This OpenVM v2.0.1 guest receives only replay input masks after the fixed
gameplay-frame-1 anchor. It derives Player motion and shooting cadence together
with the complete Reimu-A rank-1 straight-bullet pool through frame 207. The
public statement commits every intermediate Player/bullet state, 35
initializations, 30 bounds reclamations, and the final pool.

The guest rejects more than 206 transitions. The pinned retail trace first
contains an EnemyManager fired-to-collided write at frame 208, so accepting a
longer private path before Enemy/ECL composition would make the state closure
unsound.

Build an input and meter the full profile with:

```sh
python3 tools/build_player_bullet_lifecycle_openvm_input.py \
  evidence/player-bullet-lifecycle-002677-207-v1.bin \
  local/openvm/player-bullet-lifecycle-206.json \
  --report local/openvm/player-bullet-lifecycle-206-report.json

cargo openvm build \
  --manifest-path zkvm/player-bullet-lifecycle-openvm/Cargo.toml --locked
cargo openvm run \
  --manifest-path zkvm/player-bullet-lifecycle-openvm/Cargo.toml \
  --input local/openvm/player-bullet-lifecycle-206.json --mode meter --locked
```

The tracked application proof can be checked without the private trace or a
proving key:

```sh
cargo openvm verify app \
  --manifest-path zkvm/player-bullet-lifecycle-openvm/Cargo.toml \
  --proof evidence/openvm-player-bullet-lifecycle-206-v1.app.proof \
  --app-vk evidence/openvm-player-bullet-lifecycle-v1.app.vk \
  --app-commit evidence/openvm-player-bullet-lifecycle-v1.app-commit.json
```

Its 32 authenticated public bytes must equal
`e9e19abd79e48af83a3b43fc33a72f49089e83e59e328a97c3e7d1711a7a6ca3`.
The evidence manifest binds that value, the executable commitment, all source
inputs, and the frame-208 fail-closed boundary.

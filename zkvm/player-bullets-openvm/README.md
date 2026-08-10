# OpenVM Player bullet-spawn adapter

This OpenVM v2.0.1 guest proves a batch of local Reimu-A
`Player::SpawnBullets` transitions. Each private record contains one observed
pre-call player/orb position and the complete 80-slot state array. The guest
derives the power rank, timer-selected rows, lowest free slots, carried fields,
and initialized raw geometry. It also hashes every output allocation so that
geometry cannot be optimized out of the public statement.

The per-call pre-states are independently retail-bound; they are not linked to
one another. This is therefore a local callback proof, not yet the enclosing
multi-frame bullet subsystem. `UpdatePlayerBullets`, ANM termination, and Enemy
collision remain explicit open transitions.

Generate and meter the complete workload with:

```sh
python3 tools/build_player_bullets_openvm_input.py \
  evidence/player-bullets-002677-2000-v1.bin \
  local/openvm/player-bullets-1590.json \
  --calls 1590 \
  --report local/openvm/player-bullets-1590-report.json

cargo openvm build \
  --manifest-path zkvm/player-bullets-openvm/Cargo.toml --locked
cargo openvm run \
  --manifest-path zkvm/player-bullets-openvm/Cargo.toml \
  --input local/openvm/player-bullets-1590.json --mode meter --locked
```

The tracked proof can be verified without proprietary traces or proving
hardware:

```sh
cargo openvm verify app \
  --manifest-path zkvm/player-bullets-openvm/Cargo.toml \
  --proof evidence/openvm-player-bullets-1590-v1.app.proof \
  --app-vk evidence/openvm-player-bullets-v1.app.vk \
  --app-commit evidence/openvm-player-bullets-v1.app-commit.json
```

The exact public digest, source/artifact hashes, meter points, proving
resources, and negative checks are recorded in
`evidence/openvm-player-bullets-1590-v1.json`.

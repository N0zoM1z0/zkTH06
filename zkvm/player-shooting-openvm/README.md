# OpenVM Player shooting adapter

This OpenVM v2.0.1 guest executes the closed Player transition through the
`SpawnBullets` cadence boundary. The private per-frame witness remains only the
replay input mask; the initial position, life timer, focus state, previous
input, inactive fire timer, movement constants, and callback counter are fixed
or derived inside the committed guest.

The `ZKSHI1` payload contains a 20-byte header and one little-endian `u16`
input mask per transition. The guest reveals:

```text
SHA256("zkTH06/openvm/player-shooting/v1\0" || input_payload ||
       final_game_frame_le || final_x_bits_le || final_y_bits_le ||
       final_life_state || final_flags || 0x0000 || final_life_timer_le ||
       final_previous_input_le || 0x0000 || final_fire_previous_le ||
       final_fire_current_le || final_spawn_call_count_le)
```

Generate, build, meter, and verify the tracked workload with:

```sh
python3 tools/build_player_shooting_openvm_input.py \
  evidence/player-shooting-002677-2000-v1.bin \
  local/openvm/player-shooting-1999.json \
  --transitions 1999 \
  --report local/openvm/player-shooting-1999-report.json

cargo openvm build \
  --manifest-path zkvm/player-shooting-openvm/Cargo.toml --locked
cargo openvm run \
  --manifest-path zkvm/player-shooting-openvm/Cargo.toml \
  --input local/openvm/player-shooting-1999.json --mode meter --locked
cargo openvm verify app \
  --manifest-path zkvm/player-shooting-openvm/Cargo.toml \
  --proof evidence/openvm-player-shooting-1999-v1.app.proof \
  --app-vk evidence/openvm-player-shooting-v1.app.vk \
  --app-commit evidence/openvm-player-shooting-v1.app-commit.json
```

For 1,999 transitions the guest executes 5,468,598 instructions and meters
211,737,944 cells. The private payload is 4,018 bytes, and the statement binds
the final count of 1,590 callback requests. The application proof took 75.15
seconds to generate and 0.11 seconds to verify on the recorded machine.

## Claim boundary

This is a proof of the deterministic, fixed-profile Player transition through
the `SpawnBullets` call schedule. The static audit and retail/reference oracle
bind that schedule to the pinned executable, but translation validation and
complete omitted-writer noninterference remain open. The guest does not yet
execute bullet allocation or character-specific shot geometry and is not a
whole-Player or whole-game equivalence proof.

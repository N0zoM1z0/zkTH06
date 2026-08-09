# OpenVM enclosing player-state adapter

This OpenVM v2.0.1 guest executes the closed player-position/life-timer
transition in `../player-motion`.  Its private per-frame witness contains only
the replay input mask.  Character/shot configuration is read once, while the
initial position, player life state, invulnerability timer, full-speed rate,
movement bounds, inactive-bomb multipliers, and character speeds are derived
inside the committed guest.

The `ZKPSI1` payload contains a 20-byte header followed by one little-endian
`u16` input mask per transition.  The guest reveals:

```text
SHA256("zkTH06/openvm/player-state/v1\0" || input_payload ||
       final_game_frame_le || final_x_bits_le || final_y_bits_le ||
       final_life_state || final_flags || 0x0000 || final_timer_le)
```

Generate the 1,999-transition workload with:

```sh
python3 tools/build_player_state_openvm_input.py \
  evidence/player-state-002677-2000-v1.bin \
  local/openvm/player-state-1999.json \
  --transitions 1999 \
  --report local/openvm/player-state-1999-report.json
```

Build and run it with the pinned OpenVM toolchain:

```sh
cargo openvm build --manifest-path zkvm/player-state-openvm/Cargo.toml --locked
cargo openvm run --manifest-path zkvm/player-state-openvm/Cargo.toml \
  --input local/openvm/player-state-1999.json --mode meter --locked
```

Verify the tracked application proof and its authenticated statement bytes:

```sh
cargo openvm verify app \
  --manifest-path zkvm/player-state-openvm/Cargo.toml \
  --proof evidence/openvm-player-state-1999-v1.app.proof \
  --app-vk evidence/openvm-player-state-v1.app.vk \
  --app-commit evidence/openvm-player-state-v1.app-commit.json
cargo +1.91.1 run --release --locked \
  --manifest-path tools/openvm-proof-inspect/Cargo.toml -- \
  evidence/openvm-player-state-1999-v1.app.proof \
  1743dee39bbb8ec0aea47858837da4c8025929d5e31eabaa7be07fd0accff7fd
```

For 1,999 transitions the guest executes 5,412,644 instructions and meters
209,865,030 cells.  The private input is 4,018 bytes, 95.8135% smaller than the
earlier environment-record payload; cell cost is 17.4267% lower.  The recorded
application proof took 73.18 seconds to generate and 0.11 seconds to verify.
Exact executable commitment and statement digest checks pass, while one-bit-
wrong variants are rejected.

## Claim boundary

The guest removes the previous per-frame movement-environment witness.  The
current profile is deliberately fail-closed for bomb input/active bombs and
derives the reached no-hit life-state/timer sequence from a fixed post-calc
anchor.  It does not derive that anchor from registration/pre-stage execution,
model collision-driven death or respawn, execute bomb callbacks, or connect
ECL time-stop writers.  It is therefore an enclosing transition for the stated
profile, not yet the complete TH06 Player subsystem.

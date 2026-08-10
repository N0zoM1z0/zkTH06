# Player shooting transition

`zkth06-player-shooting` extends the enclosing Player position/life-timer
transition through the `Player::SpawnBullets(player, timer)` call boundary. It
derives focus state, `previousFrameInput`, fire-timer initialization and
cadence, the 30-tick reset, and the cumulative callback count from the fixed
retail anchor plus replay input.

The implementation is `no_std`, contains no floating-point operation, and
rejects bomb input/active bombs through the enclosing transition. Its current
profile fixes the dialogue predicate false and assumes full-speed timer ticks,
no collision death/respawn, and no ECL time-stop writer. Bullet-slot allocation
and character/shot callback geometry are deliberately the next refinement.

Run the unit and 1,999-transition retail-vector checks from the workspace:

```sh
cargo +1.91.1 test --manifest-path zkvm/Cargo.toml --workspace --locked
```

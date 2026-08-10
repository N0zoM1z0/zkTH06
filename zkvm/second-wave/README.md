# Stage-1 second-wave kernel

This standalone `no_std` crate continues the derived frame-249 state through
frame 350. It owns the Player bullet pool, the overlapping Sub0 Enemy slots,
ECL timers, collisions/deaths, Item allocator and motion, RNG seed/generation,
and the Enemy-bullet manager. The latter is explicitly constrained to remain
empty throughout this finite prefix; the retail/reference oracle separately
crosses the first actual Enemy-bullet spawn at frame 1180.

The transition fails closed after frame 350. Effects are sliced only after
their exact 25/55-call RNG footprint and finite pool-capacity obligation have
been retained; this is not a whole-stage equivalence claim.

Run:

```sh
cargo test --manifest-path zkvm/second-wave/Cargo.toml --locked
```

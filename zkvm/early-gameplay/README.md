# Enclosing early-gameplay kernel

This crate extends the linked Reimu-A Player/bullet transition from gameplay
frame 1 through the first real Enemy hit at frame 208. Starting from one fixed
empty anchor and replay input masks, it derives:

- five Stage-1 `Sub0` timeline spawns in stable slots;
- movement, in-bounds carry, ECL time, angle, angular velocity, and axis speed;
- Player-bullet AABB checks in manager order;
- the slot-2 fired-to-collided transition and fixed collision ANM entry;
- enemy life/death, score, and `positionOfLastEnemyHit`.

No per-frame Enemy or collision state is accepted by `step_early_gameplay`.
Malformed or out-of-profile prior states fail closed. The frame-207 Player-only
narrow phase cannot be used as another persistent state boundary: its API is
defined solely to compose the immediately following EnemyManager transition.

The selected Sub0 curve uses 40 raw binary32 axis-speed pairs indexed by the
derived ECL time 41--80. Both the pinned retail executable and independent
reference runner produce those bits, but this lookup is a partial evaluation,
not yet a machine-checked refinement of x87 `fsincos`. The static audit also
records the deliberate post-death reorder and the omitted Sub0 shooting path;
formal arithmetic refinement and slicing noninterference remain open.

The exact 207-step differential vector is
`evidence/early-gameplay-002677-208-v1.bin`. Its Rust integration test compares
every retained state at every frame. `early-gameplay-openvm` runs the same
transition with a replay-only private payload and has a tracked application
proof.

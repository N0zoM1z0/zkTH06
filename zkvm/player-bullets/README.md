# Player bullet-spawn transition

`zkth06-player-bullets` refines the Reimu-A callback path through the local
`Player::SpawnBullets` allocation and geometry boundary. It carries all 80 slot
states and the four non-laser fields that `FireSingleBullet` leaves untouched,
then derives the rank, successful bullet-data rows, lowest free slots, and raw
binary32 geometry.

The current closed profile covers power `0..31` (Reimu-A ranks 1--3), the range
reached by the pinned 2,000-frame replay prefix. Fixed velocity bits bind the
pinned executable's trigonometric results; host `sin`/`cos` is never admitted
as proof semantics. Position additions reuse the integer PC24 implementation.

This crate proves a local function transition. Per-call pre-slot states are not
yet linked across frames: `UpdatePlayerBullets`, ANM termination, and
EnemyManager collision can all change slots between calls. The crate therefore
does not claim an enclosing multi-frame bullet subsystem.

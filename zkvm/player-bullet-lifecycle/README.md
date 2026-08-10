# Player bullet lifecycle transition

This crate composes the closed Player motion/shooting state with the Reimu-A
rank-1 bullet update, 14-by-14 sprite bounds check, nonterminating straight
bullet ANM profile, age timers, slot reclamation, and `SpawnBullets` allocation.
It begins from the fixed gameplay-frame-1 Player anchor and an entirely empty
80-slot pool; subsequent pre-spawn occupancy is derived rather than supplied.

The first finite profile ends at gameplay frame 207. EnemyManager first changes
a Player bullet from fired to collided at frame 208 in the pinned replay, so
crossing that boundary without deriving Enemy state would lose soundness. The
crate therefore rejects another step at the profile boundary. It does not yet
model homing, collision, collision ANM, power/item writes, lasers, or other shot
routes.

# OpenVM complete first-wave adapter

This OpenVM v2.0.1 guest receives only the 228 replay input masks after the
fixed gameplay-frame-1 anchor. It derives the enclosing Reimu-A Player and
complete 80-slot bullet pool, five Stage-1 `Sub0` enemies, five collisions and
deaths, target selection, and score through the end of the first wave at frame
229.

The private payload is 480 bytes. No Player, bullet, Enemy, ECL, collision,
life, or score value is supplied as a witness. The public digest commits every
active-bullet and Enemy raw-bit projection at every frame.

The proof boundary is finite and route-specific. Death effects, RNG, Enemy
bullets, and spawned items are not retained; dual-oracle evidence shows that
their first feedback into retained score/power is the item collection at frame
249. Extending beyond that boundary therefore requires composing Item state.

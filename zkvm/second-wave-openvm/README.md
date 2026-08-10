# OpenVM second-wave proof

The private payload contains only the fixed profile and 350 replay input
masks. The guest re-derives frame 249 from the fixed frame-1 anchor, executes
the 101 second-wave transitions through frame 350, commits every incremental
state, and reveals one SHA-256 statement digest.

No Enemy, ECL, RNG, Item, Player-bullet, or Enemy-bullet intermediate state is
accepted as witness data.

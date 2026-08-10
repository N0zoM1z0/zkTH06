# First Item feedback transition

This standalone `no_std` crate composes the first-wave kernel with the first
gameplay-relevant Item path in the pinned Stage-1 replay. Starting at the
derived frame-208 collision state, it tracks the random-drop cursor, derives
the sole small-power Item spawn, advances its binary32 position and velocity,
checks the Player collection AABB, and applies the frame-249 score, power, and
subrank writes.

The transition also continues the complete Player-bullet pool after the
first-wave endpoint, including deterministic collision-ANM reclamation. It
fails closed after frame 249 because the next Enemy wave and its RNG/ECL state
have not yet been composed.

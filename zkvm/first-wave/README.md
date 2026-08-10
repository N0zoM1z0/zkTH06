# Complete first-wave transition

This `no_std` crate continues from the frame-208 state derived by
`zkth06-early-gameplay`. It replaces the former single collision marker with a
complete 80-slot state map, updates both fired and collided Reimu-A rank-1
bullets, and derives the remaining first-wave Enemy collisions, deaths,
target, and score through frame 229.

The transition takes only the prior closed state and one replay input mask. A
retail-bound vector reconstructs frames 1--208 with the parent kernel and then
checks every active-bullet and Enemy field through the frame-229 endpoint.

This is a finite profile, not complete gameplay. Death effects and Item state
are omitted because they do not feed the retained projection through frame
229. The first observed feedback is a small-power item collection at frame
249; the kernel refuses to cross that boundary until Item state is composed.
Direct collision-ANM decoding, RNG/effect and Sub0-shooting noninterference,
x87 trigonometric refinement, and code correspondence remain open obligations.

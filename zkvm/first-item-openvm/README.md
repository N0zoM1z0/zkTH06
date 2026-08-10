# OpenVM first Item-feedback adapter

This OpenVM v2.0.1 guest receives only the 248 replay input masks after the
fixed gameplay-frame-1 anchor. It derives the enclosing Player, complete
Player-bullet pool, first Enemy wave, random-drop cursors, the first small
power Item's spawn and motion, and its frame-249 score/power/subrank feedback.

The private payload is 520 bytes. No Player, bullet, Enemy, Item, collision,
score, power, subrank, or allocator value is witness supplied. The public
digest commits the complete retained raw-bit projection at every frame.

The tracked application proof, verifier assets, workload bindings, meter data,
and negative commitment checks are recorded in
[`../../evidence/openvm-first-item-248-v1.json`](../../evidence/openvm-first-item-248-v1.json).
The authenticated public digest is
`552ea02d7946a1da7c2cc1d7d0a9600ea21156cb2a1aa4842ef7623d6dd19cc6`.

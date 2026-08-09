# Differential evidence

This directory keeps compact, proprietary-byte-free summaries of local
experiments whose full traces cannot be reproduced in public CI without a
legally supplied TH06 v1.02h installation.  Each summary pins the executable,
replay, trace hashes, tool environment, observed projection, and explicit
claim boundary.

`retail-reference-002677-2000-v1.json` is the first shipped-executable anchor.
It compares 2,000 post-calc frames from the Wine-run retail executable with the
Linux reference runner.  The compared 34-field projection matches on every
frame, including the complete environment consumed by the player-position
slice.  This is finite differential evidence, not whole-state equivalence and
not a formal proof.

`player-motion-002677-2000-v1.bin` and its JSON manifest retain 1,999
consecutive position transitions derived from that matched retail trace.  The
fixed-width vector contains numeric inputs, environment fields, and expected
raw binary32 positions only; it contains no executable, DAT, or replay bytes.
It is a regression oracle for the narrow player-position kernel, not an
independent proof of its arithmetic or source correspondence.

`openvm-player-motion-1999-v1.json` records the first real backend milestone.
The adjacent OpenVM v2.0.1 application proof, verifying key, executable, and
expected executable-commitment descriptor are tracked so verification needs
neither retail data nor proving hardware.  The guest executes all 1,999
transitions and publishes
`SHA256(domain || private workload || computed final x/y)`; direct SDK decoding
confirmed that the proof's 32 authenticated public bytes equal the independently
computed statement digest.  The manifest binds every artifact and guest source
by SHA-256 and records meter/prove/verify results.  This proves the exact sliced
program and hash-bound workload/result, not derivation of its eleven environment
words from a complete TH06 state.  The optional pinned SDK utility under
`tools/openvm-proof-inspect/` makes the public-value comparison reproducible;
it complements rather than replaces cryptographic proof verification.

The raw retail/reference JSONL files, debugger logs, executable, DAT archives,
and generated Wine directory stay under ignored local storage.

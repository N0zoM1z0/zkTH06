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

The raw retail/reference JSONL files, debugger logs, executable, DAT archives,
and generated Wine directory stay under ignored local storage.

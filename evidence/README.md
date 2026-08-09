# Differential evidence

This directory keeps compact, proprietary-byte-free summaries of local
experiments whose full traces cannot be reproduced in public CI without a
legally supplied TH06 v1.02h installation.  Each summary pins the executable,
replay, trace hashes, tool environment, observed projection, and explicit
claim boundary.

`retail-reference-002677-2000-v1.json` is the first shipped-executable anchor.
It compares 2,000 post-calc frames from the Wine-run retail executable with the
Linux reference runner.  The compared 23-field projection matches on every
frame.  This is finite differential evidence, not whole-state equivalence and
not a formal proof.

The raw retail/reference JSONL files, debugger logs, executable, DAT archives,
and generated Wine directory stay under ignored local storage.

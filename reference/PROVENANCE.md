# Reference snapshot provenance

`reference/` is a supporting, modified source snapshot. It is deliberately not
the root project and its upstream Git history was not imported into zkTH06.

## Pinned sources

| Source | Revision | Role |
| --- | --- | --- |
| [`GensokyoClub/th06`](https://github.com/GensokyoClub/th06) | `cc475a0bc3fef38683b0f02224c87ddba0a021d9` | Reverse-engineered TH06 v1.02h source and matching specification |
| [`N0zoM1z0/th06-headless`](https://github.com/N0zoM1z0/th06-headless) | `294a4784631161306792776e51770859d0529fb3` | Portable Linux/headless adaptation used as the import snapshot |

The reconstruction is not an official Team Shanghai Alice source release. The
target is the Japanese v1.02h executable whose SHA-256 is
`9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245`.

## zkTH06 modifications

Relative to the pinned headless snapshot, this directory adds:

- strict, owning `.rpy` loading with structural and input-stream bounds;
- standalone `--replay-info` validation without proprietary game data;
- direct deterministic replay playback using the complete recorded mask;
- bounded replay cursors and fail-closed playback errors;
- deterministic playback terminals and richer diagnostic traces; and
- canonical revision-0.2 subsystem tracing with fail-closed output and
  future-live ANM field guards;
- a retail-anchor-compatible JSONL projection for configured/effective rate,
  Player life/position, respawn and active-bomb state, all invulnerability
  timer words, movement bounds, bomb multipliers, and character speeds; and
- headless-only `Player::SpawnBullets` entry/exit instrumentation for complete
  slot states, dormant carry fields, active bullet geometry/timers, and the
  first ANM projection. The scope object records diagnostics only while a trace
  is active and does not alter gameplay state.

The narrow JSONL projection is compared against an address-bound retail Wine
probe outside this directory. Broad field-level export for the eleven canonical
subsystems remains future work. Proof-kernel, formal, arithmetic-audit, and
zkVM-specific code belongs outside this directory.

## License and assets

The GensokyoClub reconstruction is published under CC0. The portable/headless
adaptation and this distributed snapshot are covered by the repository's
GPL-3.0 license. Source links above preserve attribution even though this
repository intentionally uses a flattened import rather than upstream commit
ancestry.

No original executable, game archive, music, replay corpus, generated binary,
or other proprietary asset is included.

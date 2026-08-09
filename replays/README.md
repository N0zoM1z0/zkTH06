# TH06 replay samples

These are unmodified user-created Touhou 6 v1.02h replay files used only as
local compatibility fixtures.  Do not treat the replay header or its per-stage
snapshots as trusted proof inputs: the game restores those snapshots directly
when playback enters a stage.

| File | Character / difficulty | Source | SHA-256 |
| --- | --- | --- | --- |
| `samples/th6_ud000232.rpy` | Reimu B / Lunatic | [TH6 replay strategy page](https://wikiwiki.jp/thk/%E7%B4%85/Mus) ([direct file](http://chisarin.mydns.jp/thrpyloda/replay/th6_ud000232.rpy)) | `22e03aca353d140e268ca962f3934b5e1b67f74d1c654b876c56c224abea8e24` |
| `samples/th6_ud000134.rpy` | Marisa B / Lunatic | [TH6 replay strategy page](https://wikiwiki.jp/thk/%E7%B4%85/Mus) ([direct file](http://chisarin.mydns.jp/thrpyloda/replay/th6_ud000134.rpy)) | `7a0de1f12d20b66678f382de1354ab2ee6a0f6ae719e51f06b6c3d6ec01a6ebc` |
| `samples/th6_ud002677.rpy` | Reimu A / Normal, no-miss no-bomb full-spell | [TH6 replay strategy page](https://wikiwiki.jp/thk/%E7%B4%85/Mus) ([direct file](http://chisarin.mydns.jp/thrpyloda/replay/th6_ud002677.rpy)) | `01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f` |
| `samples/th6_udLuRB.rpy` | Reimu B / Lunatic, 804,515,970 | [Touhou world records](https://maribelhearn.com/wr?hl=en-us) ([direct file](https://maribelhearn.com/media/replays/th6_udLuRB.rpy)) | `9132cbb204a8e413e4d48c4976abba00d625cdbd970a402de85c935f20ae7582` |

All four files have `T6RP` magic, version `0x0102`, six stage sections, and a
valid checksum under the game's own algorithm.  The checksum is accidental
corruption detection, not authentication.

Inspect them reproducibly with:

```sh
python3 tools/replay_info.py replays/samples/*.rpy
```

The world-record archive asks that its replay files not be reuploaded.  Keep
that sample as a local fixture rather than redistributing it from this project.

# TH06 retail-data identity

The reference runner needs data from a user-supplied Japanese Touhou Koumakyou
v1.02h installation. zkTH06 tracks the required filenames and cryptographic
identities in [`manifest.json`](manifest.json), but does not redistribute the
commercial executable or archives in this public repository.

The initial local source was the archive:

```text
[th06] 东方红魔乡 (日文版).rar
SHA-256 6b013b24c101ae846b97a2778abf461d537640611a835824a42533c692be55d6
```

After extracting a legally obtained copy, verify the minimal runtime directory:

```sh
python3 tools/verify_game_data.py /path/to/extracted/th06
```

For local development it may be placed at `data/imported/` or anywhere outside
the repository. `data/imported/` is ignored. Compatibility playback must use
that directory as its working directory so the reconstructed filesystem sees
the expected DAT filenames.

The executable is pinned for original-run comparison only. The Linux reference
runner does not execute or link it.

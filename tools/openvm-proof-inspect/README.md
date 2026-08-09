# OpenVM application-proof public-value inspector

OpenVM v2.0.1's `verify app` command authenticates the application proof,
executable commitment, and public-values Merkle path, but does not print those
public bytes. This optional host utility deserializes the same proof through the
pinned OpenVM SDK and compares its 32 public bytes with an expected SHA-256
digest.

Run it only after the cryptographic verification command documented in
`zkvm/player-motion-openvm/README.md`:

```sh
cargo +1.91.1 run --release --locked \
  --manifest-path tools/openvm-proof-inspect/Cargo.toml -- \
  evidence/openvm-player-motion-1999-v1.app.proof \
  21e195a5a5a123c01d9f48c876949340f6922e55215ced83d74dd06a988f84e6
```

This tool intentionally stays outside CI because compiling the host SDK is far
heavier than verifying the repository's structural hashes. It does not verify
the proof cryptographically by itself; both commands are required.

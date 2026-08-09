# OpenVM player-position adapter

This standalone package compiles the shared player-position kernel to OpenVM
v2.0.1's RV32IM guest target. It is excluded from the lightweight parent Cargo
workspace so normal kernel tests do not download or compile the proving stack.
The generated vm executable includes OpenVM components offered under MIT or
Apache-2.0; this bundle selects and retains OpenVM's MIT notice in
`LICENSE-OPENVM-MIT`. Exact dependency revisions and package license expressions
remain pinned in `Cargo.lock`.

The guest reads one private `ZKPMI1` byte stream. Its 24-byte header contains a
schema version, transition count, and initial raw x/y bits. Each 48-byte record
contains an input mask, player/time gate, and the eleven raw movement
environment words. The guest chains every transition and reveals one 32-byte
public statement digest:

```text
SHA256("zkTH06/openvm/player-motion/v1\0" || input_payload ||
       final_x_bits_le || final_y_bits_le)
```

The eight revealed `u32` words are the digest bytes interpreted little-endian
in consecutive four-byte chunks. The generated report records both the raw
digest and the words expected from the retail-derived vector. Hashing the
validated payload and computed endpoint binds the private workload and result
without weakening SHA-256 to fit the default 32-byte OpenVM public-value area.

Generate the tracked retail-prefix workload under ignored local storage:

```sh
python3 tools/build_player_motion_openvm_input.py \
  evidence/player-motion-002677-2000-v1.bin \
  local/openvm/player-motion-1999.json \
  --transitions 1999 \
  --report local/openvm/player-motion-1999-report.json
```

Build and meter the guest:

```sh
cargo openvm build --manifest-path zkvm/player-motion-openvm/Cargo.toml --locked
cargo openvm run --manifest-path zkvm/player-motion-openvm/Cargo.toml \
  --input local/openvm/player-motion-1999.json --mode meter --locked
```

An application proof can then be generated with:

```sh
cargo openvm keygen --manifest-path zkvm/player-motion-openvm/Cargo.toml \
  --app-only
cargo openvm prove app \
  --manifest-path zkvm/player-motion-openvm/Cargo.toml \
  --input local/openvm/player-motion-1999.json \
  --proof local/openvm/player-motion-1999.app.proof --locked
```

The tracked proof verifies without regenerating a proving key or workload:

```sh
cargo openvm verify app \
  --manifest-path zkvm/player-motion-openvm/Cargo.toml \
  --proof evidence/openvm-player-motion-1999-v1.app.proof \
  --app-vk evidence/openvm-player-motion-v1.app.vk \
  --app-commit evidence/openvm-player-motion-v1.app-commit.json
```

Then compare the authenticated public bytes with the independently expected
statement digest:

```sh
cargo +1.91.1 run --release --locked \
  --manifest-path tools/openvm-proof-inspect/Cargo.toml -- \
  evidence/openvm-player-motion-1999-v1.app.proof \
  21e195a5a5a123c01d9f48c876949340f6922e55215ced83d74dd06a988f84e6
```

The expected-commit descriptor deliberately sets its schema-required
`app_vm_commit` field to canonical zero: OpenVM v2.0.1's `verify app` path reads
only `app_exe_commit`. The evidence manifest also records an SDK-level decode
of the proof's authenticated public values and their equality to the expected
statement digest.

## Claim boundary

This adapter proves execution of the position kernel for a private transcript
bound into the public statement digest. The movement environment is still
witness-provided rather than derived from a complete TH06 state. The committed
retail-derived workload therefore supplies regression evidence, but a prover
could commit a different internally valid environment unless a later enclosing
transition derives it from committed gameplay state. Consequently, even a
valid OpenVM proof is not yet a proof of a retail replay, survival, stage clear,
or whole-game equivalence. Its purpose is to bind the exact shared Rust
transition and a specific workload/result pair to a real zkVM executable and
establish an honest cost baseline before enlarging the statement.
No zero-knowledge/privacy property is evaluated in this milestone; the source
vector is already public, and the experiment concerns execution integrity and
cost.

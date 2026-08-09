#!/usr/bin/env python3
"""Cross-check the C++ canonical writer against the Python decoder."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import canonical_trace  # noqa: E402


def expect_invalid(path: Path, expected_fragment: str) -> None:
    try:
        canonical_trace.read_trace(path)
    except canonical_trace.CanonicalTraceError as error:
        if expected_fragment not in str(error):
            raise AssertionError(f"expected {expected_fragment!r} in {error!r}") from error
    else:
        raise AssertionError(f"expected invalid canonical trace: {path}")


def main() -> int:
    binary = (Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "reference" / "th06").resolve()
    with tempfile.TemporaryDirectory(prefix="zkth06-canonical-") as directory:
        fixture = Path(directory) / "fixture.bin"
        completed = subprocess.run(
            [str(binary), "--canonical-self-test", str(fixture)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        expected_schema = canonical_trace.SCHEMA_DIGEST.hex()
        assert f"schema_sha256={expected_schema}" in completed.stdout
        assert f"record_size={canonical_trace.RECORD_SIZE}" in completed.stdout

        header, records = canonical_trace.read_trace(fixture)
        assert fixture.stat().st_size == canonical_trace.HEADER_SIZE + canonical_trace.RECORD_SIZE
        assert header.initial_seed == 0x1234
        assert header.difficulty == 2
        assert header.character == 1
        assert header.shot_type == 0
        assert header.start_stage == 4
        assert header.run_mode == 2
        assert len(records) == 1
        record = records[0]
        assert record.tick == 0x0102030405060708
        assert record.game_frame == 12345
        assert record.stage == 4
        assert record.input_mask == 0x55AA
        assert record.terminal_reason == 6
        assert record.flags == 3
        assert record.supervisor_state == 7
        assert len(record.subsystems) == canonical_trace.SUBSYSTEM_COUNT
        assert [subsystem.entity_count for subsystem in record.subsystems] == list(
            range(1, canonical_trace.SUBSYSTEM_COUNT + 1)
        )

        identical = Path(directory) / "identical.bin"
        shutil.copyfile(fixture, identical)
        assert canonical_trace.compare(fixture, identical) == {"equal": True, "record_count": 1}

        corrupted = Path(directory) / "corrupted.bin"
        corrupted_bytes = bytearray(fixture.read_bytes())
        corrupted_bytes[canonical_trace.HEADER_SIZE + canonical_trace.RECORD_PREFIX_SIZE + 16] ^= 0x80
        corrupted.write_bytes(corrupted_bytes)
        expect_invalid(corrupted, "root mismatch")

        truncated = Path(directory) / "truncated.bin"
        truncated.write_bytes(fixture.read_bytes()[:-1])
        expect_invalid(truncated, "truncated canonical record")

    print("validated C++/Python canonical trace wire format and corruption rejection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

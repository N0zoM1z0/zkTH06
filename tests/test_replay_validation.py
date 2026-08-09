#!/usr/bin/env python3
"""Cross-check the Python and C++ TH06 replay validators."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TRACKED_FIXTURES = (
    "th6_ud000134.rpy",
    "th6_ud000232.rpy",
    "th6_ud002677.rpy",
)

from tools.replay_info import (  # noqa: E402
    CHECKSUM_SEED,
    ReplayError,
    _deobfuscate,
    inspect_replay,
)


def run_cpp(binary: Path, replay: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), "--replay-info", str(replay)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def encode(decoded: bytearray) -> bytes:
    struct.pack_into("<I", decoded, 8, (CHECKSUM_SEED + sum(decoded[14:])) & 0xFFFFFFFF)
    encoded = bytearray(decoded)
    transform = decoded[14]
    for cursor in range(15, len(decoded)):
        encoded[cursor] = (decoded[cursor] + transform) & 0xFF
        transform = (transform + 7) & 0xFF
    return bytes(encoded)


def assert_valid_pair(binary: Path, replay: Path) -> None:
    python_report = inspect_replay(replay, include_inputs=True)
    cpp_result = run_cpp(binary, replay)
    if cpp_result.returncode != 0:
        raise AssertionError(f"C++ rejected {replay}: {cpp_result.stderr}")
    cpp_report = json.loads(cpp_result.stdout)

    assert cpp_report["valid"] is True
    assert cpp_report["size"] == python_report["size"]
    assert cpp_report["version"] == int(python_report["version"], 16)
    assert cpp_report["shot_type_character"] == python_report["shot_type_character"]
    assert cpp_report["difficulty"] == python_report["difficulty"]
    assert len(cpp_report["stages"]) == len(python_report["stages"])
    for cpp_stage, python_stage in zip(cpp_report["stages"], python_report["stages"], strict=True):
        assert cpp_stage["stage"] == python_stage["stage"]
        assert cpp_stage["offset"] == python_stage["offset"]
        assert cpp_stage["size"] == python_stage["size"]
        assert cpp_stage["records"] == python_stage["input_change_records"]
        assert cpp_stage["playback_records"] == python_stage["playback_records"]
        assert cpp_stage["terminal_frame"] == python_stage["terminal_frame"]


def assert_invalid_pair(binary: Path, replay: Path) -> None:
    try:
        inspect_replay(replay)
    except ReplayError:
        pass
    else:
        raise AssertionError(f"Python accepted malformed replay: {replay}")
    cpp_result = run_cpp(binary, replay)
    if cpp_result.returncode == 0:
        raise AssertionError(f"C++ accepted malformed replay: {replay}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()

    fixtures = [ROOT / "replays" / "samples" / name for name in TRACKED_FIXTURES]
    missing = [fixture for fixture in fixtures if not fixture.is_file()]
    if missing:
        raise AssertionError(f"missing tracked replay fixtures: {missing}")
    for fixture in fixtures:
        assert_valid_pair(binary, fixture)

    with tempfile.TemporaryDirectory(prefix="zkth06-replay-test-") as directory:
        temp = Path(directory)
        source = fixtures[0].read_bytes()

        bad_magic = temp / "bad-magic.rpy"
        magic_bytes = bytearray(source)
        magic_bytes[0] ^= 0xFF
        bad_magic.write_bytes(magic_bytes)
        assert_invalid_pair(binary, bad_magic)

        bad_checksum = temp / "bad-checksum.rpy"
        checksum_bytes = bytearray(source)
        checksum_bytes[-1] ^= 0x01
        bad_checksum.write_bytes(checksum_bytes)
        assert_invalid_pair(binary, bad_checksum)

        bad_mask = temp / "bad-mask.rpy"
        decoded = _deobfuscate(source)
        first_stage = next(offset for offset in struct.unpack_from("<7I", decoded, 52) if offset)
        struct.pack_into("<H", decoded, first_stage + 16 + 4, 0x8000)
        bad_mask.write_bytes(encode(decoded))
        assert_invalid_pair(binary, bad_mask)

    print(f"validated {len(fixtures)} replay fixtures and 3 malformed cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate deterministic construction of the Player-bullets OpenVM input."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-bullets-002677-2000-v1.bin"
BUILDER = ROOT / "tools" / "build_player_bullets_openvm_input.py"
VECTOR_HEADER_BYTES = 224
VECTOR_STATE_OFFSET = 46
INPUT_HEADER = struct.Struct("<8sII4B")
INPUT_RECORD = struct.Struct("<IHBB9I80B")
SUMMARY = struct.Struct("<8I4B32s")
STATEMENT_DOMAIN = b"zkTH06/openvm/player-bullets/v1\0"


def run_builder(vector: Path, output: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(BUILDER),
            str(vector),
            str(output),
            "--calls",
            "100",
            "--report",
            str(report),
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-player-bullets-input-") as directory:
        temporary = Path(directory)
        output = temporary / "input.json"
        report_path = temporary / "report.json"
        result = run_builder(VECTOR, output, report_path)
        assert result.returncode == 0, result.stderr
        encoded = json.loads(output.read_text(encoding="utf-8"))["input"]
        assert len(encoded) == 1 and encoded[0].startswith("0x01")
        payload = bytes.fromhex(encoded[0][4:])
        magic, schema, calls, character, shot_type, maximum_rank, profile_flags = (
            INPUT_HEADER.unpack_from(payload)
        )
        assert magic == b"ZKPBI1\0\0"
        assert schema == 1 and calls == 100
        assert (character, shot_type, maximum_rank, profile_flags) == (0, 0, 3, 1)
        assert len(payload) == INPUT_HEADER.size + calls * INPUT_RECORD.size

        report_text = report_path.read_text(encoding="utf-8")
        assert str(temporary) not in report_text
        report = json.loads(report_text)
        assert report["source_vector_sha256"] == hashlib.sha256(VECTOR.read_bytes()).hexdigest()
        assert report["input_payload_sha256"] == hashlib.sha256(payload).hexdigest()
        assert report["spawn_calls"] == 100
        summary = SUMMARY.pack(
            report["selected_last_game_frame"],
            report["spawn_calls"],
            report["initialized_bullets"],
            report["rank_call_counts"]["1"],
            report["rank_call_counts"]["2"],
            report["rank_call_counts"]["3"],
            report["zero_allocation_calls"],
            report["maximum_pre_call_active_slots"],
            report["character"],
            report["shot_type"],
            report["maximum_rank"],
            report["profile_flags"],
            bytes.fromhex(report["expected_geometry_sha256"]),
        )
        statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
        assert report["expected_statement_sha256"] == statement.hex()
        assert report["expected_public_u32"] == list(struct.unpack("<8I", statement))

        tampered = bytearray(VECTOR.read_bytes())
        tampered[VECTOR_HEADER_BYTES + VECTOR_STATE_OFFSET] = 3
        tampered_path = temporary / "tampered.bin"
        tampered_path.write_bytes(tampered)
        rejected = run_builder(tampered_path, output, report_path)
        assert rejected.returncode != 0
        assert "invalid slot states" in rejected.stderr

    print("validated deterministic Player-bullets OpenVM input and statement construction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

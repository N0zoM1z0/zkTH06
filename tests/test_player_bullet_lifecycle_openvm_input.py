#!/usr/bin/env python3
"""Validate deterministic linked-lifecycle OpenVM input construction."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-bullet-lifecycle-002677-207-v1.bin"
BUILDER = ROOT / "tools" / "build_player_bullet_lifecycle_openvm_input.py"
INPUT_HEADER = struct.Struct("<8sII4BI")
SUMMARY = struct.Struct("<7I32s")
STATEMENT_DOMAIN = b"zkTH06/openvm/player-bullet-lifecycle/v1\0"
VECTOR_HEADER_BYTES = 232
VECTOR_FRAME_BYTES = 40
FIRST_BULLET_AGE_SUBFRAME_OFFSET = VECTOR_HEADER_BYTES + 34 * VECTOR_FRAME_BYTES + 40 + 60


def run_builder(
    vector: Path, output: Path, report: Path, transitions: int = 100
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(BUILDER),
            str(vector),
            str(output),
            "--transitions",
            str(transitions),
            "--report",
            str(report),
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zkth06-lifecycle-openvm-input-") as directory:
        temporary = Path(directory)
        output = temporary / "input.json"
        report_path = temporary / "report.json"
        result = run_builder(VECTOR, output, report_path)
        assert result.returncode == 0, result.stderr
        encoded = json.loads(output.read_text(encoding="utf-8"))["input"]
        assert len(encoded) == 1 and encoded[0].startswith("0x01")
        payload = bytes.fromhex(encoded[0][4:])
        magic, schema, count, character, shot, flags, reserved, anchor = INPUT_HEADER.unpack_from(
            payload
        )
        assert magic == b"ZKPLI1\0\0"
        assert (schema, count, character, shot, flags, reserved, anchor) == (
            1,
            100,
            0,
            0,
            1,
            0,
            1,
        )
        assert len(payload) == INPUT_HEADER.size + 2 * count

        report_text = report_path.read_text(encoding="utf-8")
        assert str(temporary) not in report_text
        report = json.loads(report_text)
        assert report["source_vector_sha256"] == hashlib.sha256(VECTOR.read_bytes()).hexdigest()
        assert report["input_payload_sha256"] == hashlib.sha256(payload).hexdigest()
        assert report["transitions"] == 100
        summary = SUMMARY.pack(
            report["expected_final_game_frame"],
            report["transitions"],
            report["expected_spawn_calls"],
            report["expected_initialized_bullets"],
            report["expected_update_reclamations"],
            report["expected_final_active_slots"],
            report["expected_maximum_active_slots"],
            bytes.fromhex(report["expected_lifecycle_sha256"]),
        )
        statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
        assert report["expected_statement_sha256"] == statement.hex()
        assert report["expected_public_u32"] == list(struct.unpack("<8I", statement))

        tampered = bytearray(VECTOR.read_bytes())
        struct.pack_into("<I", tampered, FIRST_BULLET_AGE_SUBFRAME_OFFSET, 1)
        tampered_path = temporary / "tampered.bin"
        tampered_path.write_bytes(tampered)
        rejected = run_builder(tampered_path, output, report_path)
        assert rejected.returncode != 0
        assert "invalid active bullet" in rejected.stderr

    print("validated deterministic linked-lifecycle OpenVM input and public statement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

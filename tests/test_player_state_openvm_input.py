#!/usr/bin/env python3
"""Validate deterministic construction of the closed OpenVM workload."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-state-002677-2000-v1.bin"
VECTOR_MANIFEST = ROOT / "evidence" / "player-state-002677-2000-v1.json"
BUILDER = ROOT / "tools" / "build_player_state_openvm_input.py"
VECTOR_HEADER_BYTES = 160
VECTOR_RECORD_BYTES = 20
INPUT_HEADER = struct.Struct("<8sIIBBBB")
FINAL_STATE = struct.Struct("<IIIBB2xi")
STATEMENT_DOMAIN = b"zkTH06/openvm/player-state/v1\0"


def run_builder(vector: Path, output: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(BUILDER),
            str(vector),
            str(output),
            "--transitions",
            "3",
            "--report",
            str(report),
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-state-input-") as directory:
        temporary = Path(directory)
        output = temporary / "input.json"
        report_path = temporary / "report.json"
        result = run_builder(VECTOR, output, report_path)
        assert result.returncode == 0, result.stderr
        encoded = json.loads(output.read_text(encoding="utf-8"))["input"]
        assert len(encoded) == 1 and encoded[0].startswith("0x01")
        payload = bytes.fromhex(encoded[0][4:])
        magic, schema, transitions, character, shot_type, flags, reserved = INPUT_HEADER.unpack_from(
            payload
        )
        assert magic == b"ZKPSI1\0\0"
        assert schema == 1
        assert transitions == 3
        assert (character, shot_type, flags, reserved) == (0, 0, 0, 0)
        assert len(payload) == INPUT_HEADER.size + transitions * 2

        report_text = report_path.read_text(encoding="utf-8")
        assert str(temporary) not in report_text
        report = json.loads(report_text)
        vector_manifest = json.loads(VECTOR_MANIFEST.read_text(encoding="utf-8"))
        assert report["source_vector_sha256"] == hashlib.sha256(VECTOR.read_bytes()).hexdigest()
        assert report["source_vector_sha256"] == vector_manifest["vector_sha256"]
        assert report["input_payload_sha256"] == hashlib.sha256(payload).hexdigest()
        assert report["input_payload_bytes"] == len(payload)
        final_state = FINAL_STATE.pack(
            report["expected_final_game_frame"],
            report["expected_final_x_bits"],
            report["expected_final_y_bits"],
            report["expected_final_player_state"],
            report["expected_final_flags"],
            report["expected_final_invulnerability_timer"],
        )
        statement = hashlib.sha256(STATEMENT_DOMAIN + payload + final_state).digest()
        assert report["expected_statement_sha256"] == statement.hex()
        assert report["expected_public_u32"] == list(struct.unpack("<8I", statement))

        tampered = bytearray(VECTOR.read_bytes())
        second_record_input = VECTOR_HEADER_BYTES + VECTOR_RECORD_BYTES + 4
        input_mask = struct.unpack_from("<H", tampered, second_record_input)[0]
        struct.pack_into("<H", tampered, second_record_input, input_mask | 0x0002)
        tampered_path = temporary / "tampered.bin"
        tampered_path.write_bytes(tampered)
        rejected = run_builder(tampered_path, output, report_path)
        assert rejected.returncode != 0
        assert "leaves the closed profile" in rejected.stderr

    print("validated deterministic OpenVM enclosing-state input construction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

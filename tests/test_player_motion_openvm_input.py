#!/usr/bin/env python3
"""Validate deterministic construction of the OpenVM motion workload."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-motion-002677-2000-v1.bin"
VECTOR_MANIFEST = ROOT / "evidence" / "player-motion-002677-2000-v1.json"
BUILDER = ROOT / "tools" / "build_player_motion_openvm_input.py"
INPUT_HEADER = struct.Struct("<8sIIII")
INPUT_RECORD_BYTES = 48
STATEMENT_DOMAIN = b"zkTH06/openvm/player-motion/v1\0"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-input-") as directory:
        temporary = Path(directory)
        output = temporary / "input.json"
        report_path = temporary / "report.json"
        result = subprocess.run(
            [
                "python3",
                str(BUILDER),
                str(VECTOR),
                str(output),
                "--transitions",
                "3",
                "--report",
                str(report_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        document = json.loads(output.read_text(encoding="utf-8"))
        encoded = document["input"]
        assert len(encoded) == 1 and encoded[0].startswith("0x01")
        payload = bytes.fromhex(encoded[0][4:])
        magic, schema, transitions, initial_x, initial_y = INPUT_HEADER.unpack_from(payload)
        assert magic == b"ZKPMI1\0\0"
        assert schema == 1
        assert transitions == 3
        assert len(payload) == INPUT_HEADER.size + transitions * INPUT_RECORD_BYTES

        report_text = report_path.read_text(encoding="utf-8")
        assert str(temporary) not in report_text
        report = json.loads(report_text)
        vector_manifest = json.loads(VECTOR_MANIFEST.read_text(encoding="utf-8"))
        assert report["source_vector_sha256"] == hashlib.sha256(VECTOR.read_bytes()).hexdigest()
        assert report["source_vector_sha256"] == vector_manifest["vector_sha256"]
        assert report["input_payload_sha256"] == hashlib.sha256(payload).hexdigest()
        assert report["input_payload_bytes"] == len(payload)
        assert report["transitions"] == 3
        statement = hashlib.sha256(
            STATEMENT_DOMAIN
            + payload
            + struct.pack(
                "<II",
                report["expected_final_x_bits"],
                report["expected_final_y_bits"],
            )
        ).digest()
        assert report["statement_domain_ascii"] == "zkTH06/openvm/player-motion/v1"
        assert report["expected_statement_sha256"] == statement.hex()
        assert report["expected_public_u32"] == list(struct.unpack("<8I", statement))

    print("validated deterministic OpenVM player-motion input construction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

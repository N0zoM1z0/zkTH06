#!/usr/bin/env python3
"""Check replay-only OpenVM input generation for the second-wave kernel."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "second-wave-002677-350-v1.bin"
BUILDER = ROOT / "tools" / "build_second_wave_openvm_input.py"
EXPECTED_STATEMENT = "7d70502eb31b1ad8fc13947b8ae68185df92f3799ee62ca033b21c78fd114281"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zkth06-second-wave-input-") as directory:
        output = Path(directory) / "input.json"
        report_path = Path(directory) / "report.json"
        result = subprocess.run(
            ["python3", str(BUILDER), str(VECTOR), str(output), "--report", str(report_path)],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        encoded = json.loads(output.read_text(encoding="utf-8"))["input"]
        assert len(encoded) == 1 and encoded[0].startswith("0x01")
        payload = bytes.fromhex(encoded[0][4:])
        report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(payload) == report["input_payload_bytes"] == 724
    assert hashlib.sha256(payload).hexdigest() == report["input_payload_sha256"]
    assert report["source_vector_sha256"] == hashlib.sha256(VECTOR.read_bytes()).hexdigest()
    assert report["input_frames"] == 350
    assert report["incremental_transitions"] == 101
    assert report["expected_final_game_frame"] == 350
    assert report["expected_score"] == 3910
    assert report["expected_rng_seed"] == 37443
    assert report["expected_rng_generation"] == 342
    assert report["expected_active_enemy_bullets"] == 0
    assert report["expected_statement_sha256"] == EXPECTED_STATEMENT
    assert report["claim_boundary"].startswith("private replay masks only")
    print("validated 724-byte replay-only second-wave OpenVM input")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

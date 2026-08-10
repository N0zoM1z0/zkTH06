#!/usr/bin/env python3
"""Check the tracked complete first-wave OpenVM proof bundle."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
MANIFEST = EVIDENCE / "openvm-first-wave-228-v1.json"
VECTOR = EVIDENCE / "first-wave-002677-229-v1.bin"
BUILDER = ROOT / "tools" / "build_first_wave_openvm_input.py"
STATEMENT_DOMAIN = b"zkTH06/openvm/first-wave/v1\0"
SUMMARY = struct.Struct("<9I32s")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in text
    manifest = json.loads(text)
    assert manifest["type"] == "zkth06.openvm-first-wave-proof"
    assert manifest["schema_version"] == 1
    assert manifest["backend"]["cargo_openvm_version"] == "2.0.1"
    assert manifest["backend"]["cargo_openvm_revision"].startswith("b820b25")
    assert manifest["backend"]["vm_extensions"] == ["rv32i", "rv32m", "io", "sha2"]

    workload = manifest["workload"]
    assert workload["source_vector_sha256"] == sha256(VECTOR)
    assert workload["source_vector_bytes"] == VECTOR.stat().st_size == 122_580
    assert workload["anchor_game_frame"] == 1
    assert workload["incremental_anchor_game_frame"] == 208
    assert workload["final_game_frame"] == 229
    assert workload["transitions"] == 228
    assert workload["incremental_transitions"] == 21
    assert workload["damage_calls"] == 253
    assert workload["collision_events"] == 5
    assert workload["collision_slots"] == [2, 3, 4, 0, 1]
    assert workload["collided_bullets"] == 5
    assert workload["active_bullets"] == 6
    assert workload["remaining_enemies"] == 0
    assert workload["score"] == 1950
    assert workload["input_payload_bytes"] == 480

    for group in ("source_bindings", "evidence_bindings"):
        for relative, expected in manifest[group].items():
            path = ROOT / relative
            assert path.is_file(), relative
            assert sha256(path) == expected, relative
    for relative, expected in manifest["public_values_audit"]["tool_source_bindings"].items():
        assert sha256(ROOT / relative) == expected, relative

    for name in ("vm_executable", "app_verifying_key", "app_commit_descriptor", "app_proof"):
        descriptor = manifest["artifacts"][name]
        path = EVIDENCE / descriptor["path"]
        assert path.is_file(), name
        assert path.stat().st_size == descriptor["bytes"], name
        assert sha256(path) == descriptor["sha256"], name
    commit = json.loads(
        (EVIDENCE / manifest["artifacts"]["app_commit_descriptor"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert commit["app_exe_commit"] == manifest["artifacts"]["vm_executable"]["app_exe_commit"]
    assert commit["app_vm_commit"] == "0x" + "00" * 32

    with tempfile.TemporaryDirectory(prefix="zkth06-first-wave-openvm-") as directory:
        input_path = Path(directory) / "input.json"
        report_path = Path(directory) / "report.json"
        result = subprocess.run(
            [
                "python3",
                str(BUILDER),
                str(VECTOR),
                str(input_path),
                "--transitions",
                str(workload["transitions"]),
                "--report",
                str(report_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(report_path.read_text(encoding="utf-8"))
        encoded = json.loads(input_path.read_text(encoding="utf-8"))["input"][0]
        assert encoded.startswith("0x01")
        payload = bytes.fromhex(encoded[4:])

    report_fields = {
        "source_vector_sha256": "source_vector_sha256",
        "input_payload_bytes": "input_payload_bytes",
        "input_payload_sha256": "input_payload_sha256",
        "expected_final_game_frame": "final_game_frame",
        "transitions": "transitions",
        "expected_score": "score",
        "expected_damage_calls": "damage_calls",
        "expected_collision_events": "collision_events",
        "expected_collided_bullets": "collided_bullets",
        "expected_active_bullets": "active_bullets",
        "expected_remaining_enemies": "remaining_enemies",
        "expected_maximum_enemies": "maximum_enemies",
        "expected_projection_sha256": "expected_projection_sha256",
        "expected_statement_sha256": "expected_statement_sha256",
    }
    for report_field, workload_field in report_fields.items():
        assert report[report_field] == workload[workload_field], report_field
    summary = SUMMARY.pack(
        workload["final_game_frame"],
        workload["transitions"],
        workload["score"],
        workload["damage_calls"],
        workload["collision_events"],
        workload["collided_bullets"],
        workload["active_bullets"],
        workload["remaining_enemies"],
        workload["maximum_enemies"],
        bytes.fromhex(workload["expected_projection_sha256"]),
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    assert statement.hex() == workload["expected_statement_sha256"]
    public = manifest["public_values_audit"]
    assert public["decoded_bytes"] == list(statement)
    assert public["matches_expected_statement_sha256"] is True
    assert public["one_bit_wrong_expected_digest_rejected"] is True
    assert [row["transitions"] for row in manifest["meter"]] == [1, 10, 100, 207, 228]
    assert manifest["meter"][-1]["statement_sha256"] == workload["expected_statement_sha256"]
    assert all(row["instructions"] > 0 and row["cells"] > 0 for row in manifest["meter"])
    assert all(manifest["verification"].values())
    assert "frame 249" in manifest["claim_boundary"]
    assert "using only replay input masks" in manifest["claim_boundary"]
    assert "five collision transitions" in manifest["claim_boundary"]
    assert manifest["backend"]["cargo_openvm_revision"] in (
        ROOT / "zkvm" / "first-wave-openvm" / "Cargo.lock"
    ).read_text(encoding="utf-8")
    print("validated tracked OpenVM complete first-wave proof bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

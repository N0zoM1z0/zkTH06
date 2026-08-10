#!/usr/bin/env python3
"""Check the tracked enclosing early-gameplay OpenVM proof bundle."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence"
MANIFEST = EVIDENCE_DIR / "openvm-early-gameplay-207-v1.json"
VECTOR = EVIDENCE_DIR / "early-gameplay-002677-208-v1.bin"
BUILDER = ROOT / "tools" / "build_early_gameplay_openvm_input.py"
STATEMENT_DOMAIN = b"zkTH06/openvm/early-gameplay/v1\0"
SUMMARY = struct.Struct("<8I32s")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["type"] == "zkth06.openvm-early-gameplay-proof"
    assert manifest["schema_version"] == 1
    assert manifest["backend"]["cargo_openvm_version"] == "2.0.1"
    assert manifest["backend"]["cargo_openvm_revision"].startswith("b820b25")
    assert manifest["backend"]["vm_extensions"] == ["rv32i", "rv32m", "io", "sha2"]

    workload = manifest["workload"]
    assert workload["source_vector_sha256"] == sha256(VECTOR)
    assert workload["source_vector_bytes"] == VECTOR.stat().st_size == 14_780
    assert workload["anchor_game_frame"] == 1
    assert workload["final_game_frame"] == 208
    assert workload["transitions"] == 207
    assert workload["damage_calls"] == 200
    assert workload["collision_events"] == 1
    assert workload["collided_slot"] == 2
    assert workload["maximum_enemies"] == 5
    assert workload["remaining_enemies"] == 4
    assert workload["score"] == 390
    assert workload["input_payload_bytes"] == 438
    assert workload["statement_domain_ascii"] == STATEMENT_DOMAIN[:-1].decode("ascii")

    for binding_group in ("source_bindings", "evidence_bindings"):
        for relative, expected_hash in manifest[binding_group].items():
            path = ROOT / relative
            assert path.is_file(), relative
            assert sha256(path) == expected_hash, relative
    for relative, expected_hash in manifest["public_values_audit"][
        "tool_source_bindings"
    ].items():
        path = ROOT / relative
        assert path.is_file(), relative
        assert sha256(path) == expected_hash, relative

    artifacts = manifest["artifacts"]
    for name in ("vm_executable", "app_verifying_key", "app_commit_descriptor", "app_proof"):
        descriptor = artifacts[name]
        path = EVIDENCE_DIR / descriptor["path"]
        assert path.is_file(), name
        assert path.stat().st_size == descriptor["bytes"], name
        assert sha256(path) == descriptor["sha256"], name
    commit = json.loads(
        (EVIDENCE_DIR / artifacts["app_commit_descriptor"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert commit["app_exe_commit"] == artifacts["vm_executable"]["app_exe_commit"]
    assert commit["app_vm_commit"] == "0x" + "00" * 32

    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-early-gameplay-evidence-") as directory:
        temporary = Path(directory)
        input_path = temporary / "input.json"
        report_path = temporary / "report.json"
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
        "expected_collided_slot": "collided_slot",
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
        workload["collided_slot"],
        workload["remaining_enemies"],
        workload["maximum_enemies"],
        bytes.fromhex(workload["expected_projection_sha256"]),
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    assert statement.hex() == workload["expected_statement_sha256"]
    audit = manifest["public_values_audit"]
    assert audit["decoded_bytes"] == list(statement)
    assert audit["matches_expected_statement_sha256"] is True
    assert audit["one_bit_wrong_expected_digest_rejected"] is True

    meter = manifest["meter"]
    assert [row["transitions"] for row in meter] == [1, 10, 100, 207]
    assert all(row["instructions"] > 0 and row["cells"] > 0 for row in meter)
    assert meter[-1]["statement_sha256"] == workload["expected_statement_sha256"]
    verification = manifest["verification"]
    assert verification["expected_executable_commit_accepted"] is True
    assert verification["one_bit_wrong_executable_commit_rejected"] is True
    assert verification["public_statement_digest_matches"] is True
    assert verification["one_bit_wrong_public_digest_rejected"] is True

    iteration = manifest["design_iteration"]
    assert iteration["enclosing_gameplay_payload_bytes"] == workload["input_payload_bytes"]
    assert iteration["payload_increase_bytes"] == 2
    boundary = manifest["claim_boundary"]
    assert "using only replay input masks" in boundary
    assert "200 AABB damage calls" in boundary
    assert "x87 fsincos refinement" in boundary
    assert "not a universal retail-binary equivalence proof" in boundary

    lock_text = (ROOT / "zkvm" / "early-gameplay-openvm" / "Cargo.lock").read_text(
        encoding="utf-8"
    )
    assert manifest["backend"]["cargo_openvm_revision"] in lock_text
    print("validated tracked OpenVM enclosing early-gameplay proof bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

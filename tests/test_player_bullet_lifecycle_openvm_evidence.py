#!/usr/bin/env python3
"""Check the tracked linked Player/bullet lifecycle OpenVM proof bundle."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence"
MANIFEST = EVIDENCE_DIR / "openvm-player-bullet-lifecycle-206-v1.json"
VECTOR = EVIDENCE_DIR / "player-bullet-lifecycle-002677-207-v1.bin"
BUILDER = ROOT / "tools" / "build_player_bullet_lifecycle_openvm_input.py"
STATEMENT_DOMAIN = b"zkTH06/openvm/player-bullet-lifecycle/v1\0"
SUMMARY = struct.Struct("<7I32s")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["type"] == "zkth06.openvm-player-bullet-lifecycle-proof"
    assert manifest["schema_version"] == 1
    assert manifest["backend"]["cargo_openvm_version"] == "2.0.1"
    assert manifest["backend"]["cargo_openvm_revision"].startswith("b820b25")
    assert manifest["backend"]["vm_extensions"] == ["rv32i", "rv32m", "io", "sha2"]

    workload = manifest["workload"]
    assert workload["source_vector_sha256"] == sha256(VECTOR)
    assert workload["source_vector_bytes"] == VECTOR.stat().st_size == 101_904
    assert workload["anchor_game_frame"] == 1
    assert workload["final_game_frame"] == 207
    assert workload["first_external_collision_game_frame"] == 208
    assert workload["transitions"] == 206
    assert workload["spawn_calls"] == 173
    assert workload["initialized_bullets"] == 35
    assert workload["update_reclamations"] == 30
    assert workload["maximum_active_slots"] == 7
    assert workload["final_active_slots"] == 5
    assert workload["input_payload_bytes"] == 436
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

    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-bullet-lifecycle-evidence-") as directory:
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
        "expected_spawn_calls": "spawn_calls",
        "expected_initialized_bullets": "initialized_bullets",
        "expected_update_reclamations": "update_reclamations",
        "expected_final_active_slots": "final_active_slots",
        "expected_maximum_active_slots": "maximum_active_slots",
        "expected_lifecycle_sha256": "expected_lifecycle_sha256",
        "expected_statement_sha256": "expected_statement_sha256",
    }
    for report_field, workload_field in report_fields.items():
        assert report[report_field] == workload[workload_field], report_field
    summary = SUMMARY.pack(
        workload["final_game_frame"],
        workload["transitions"],
        workload["spawn_calls"],
        workload["initialized_bullets"],
        workload["update_reclamations"],
        workload["final_active_slots"],
        workload["maximum_active_slots"],
        bytes.fromhex(workload["expected_lifecycle_sha256"]),
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    assert statement.hex() == workload["expected_statement_sha256"]
    audit = manifest["public_values_audit"]
    assert audit["decoded_bytes"] == list(statement)
    assert audit["matches_expected_statement_sha256"] is True
    assert audit["one_bit_wrong_expected_digest_rejected"] is True

    meter = manifest["meter"]
    assert [row["transitions"] for row in meter] == [1, 10, 100, 206]
    assert all(row["instructions"] > 0 and row["cells"] > 0 for row in meter)
    assert meter[-1]["statement_sha256"] == workload["expected_statement_sha256"]
    verification = manifest["verification"]
    assert verification["expected_executable_commit_accepted"] is True
    assert verification["one_bit_wrong_executable_commit_rejected"] is True
    assert verification["public_statement_digest_matches"] is True
    assert verification["one_bit_wrong_public_digest_rejected"] is True

    iteration = manifest["design_iteration"]
    assert iteration["enclosing_lifecycle_payload_bytes"] == workload["input_payload_bytes"]
    assert iteration["payload_reduction_bytes"] == 197_180 - 436
    boundary = manifest["claim_boundary"]
    assert "using only replay input masks" in boundary
    assert "fails closed after frame 207" in boundary
    assert "not a proof of Enemy/ECL collision" in boundary

    lock_text = (ROOT / "zkvm" / "player-bullet-lifecycle-openvm" / "Cargo.lock").read_text(
        encoding="utf-8"
    )
    assert manifest["backend"]["cargo_openvm_revision"] in lock_text
    print("validated tracked OpenVM linked Player/bullet lifecycle proof bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

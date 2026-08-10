#!/usr/bin/env python3
"""Check the tracked Player-bullets OpenVM proof and source bindings."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence"
MANIFEST = EVIDENCE_DIR / "openvm-player-bullets-1590-v1.json"
VECTOR = EVIDENCE_DIR / "player-bullets-002677-2000-v1.bin"
BUILDER = ROOT / "tools" / "build_player_bullets_openvm_input.py"
STATEMENT_DOMAIN = b"zkTH06/openvm/player-bullets/v1\0"
SUMMARY = struct.Struct("<8I4B32s")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["type"] == "zkth06.openvm-player-bullets-proof"
    assert manifest["schema_version"] == 1
    assert manifest["backend"]["cargo_openvm_version"] == "2.0.1"
    assert manifest["backend"]["cargo_openvm_revision"].startswith("b820b25")
    assert manifest["backend"]["vm_extensions"] == ["rv32i", "rv32m", "io", "sha2"]

    workload = manifest["workload"]
    assert workload["source_vector_sha256"] == sha256(VECTOR)
    assert workload["source_vector_bytes"] == VECTOR.stat().st_size
    assert workload["spawn_calls"] == 1_590
    assert workload["initialized_bullets"] == 422
    assert workload["input_payload_bytes"] == 197_180
    assert workload["statement_domain_ascii"] == STATEMENT_DOMAIN[:-1].decode("ascii")

    for binding_group in ("source_bindings", "evidence_bindings"):
        for relative, expected_hash in manifest[binding_group].items():
            path = ROOT / relative
            assert path.is_file(), relative
            assert sha256(path) == expected_hash, relative
    for relative, expected_hash in manifest["public_values_audit"]["tool_source_bindings"].items():
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
        (EVIDENCE_DIR / artifacts["app_commit_descriptor"]["path"]).read_text(encoding="utf-8")
    )
    assert commit["app_exe_commit"] == artifacts["vm_executable"]["app_exe_commit"]
    assert commit["app_vm_commit"] == "0x" + "00" * 32

    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-player-bullets-evidence-") as directory:
        temporary = Path(directory)
        input_path = temporary / "input.json"
        report_path = temporary / "report.json"
        result = subprocess.run(
            [
                "python3",
                str(BUILDER),
                str(VECTOR),
                str(input_path),
                "--calls",
                str(workload["spawn_calls"]),
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

    for field in (
        "source_vector_sha256",
        "input_payload_bytes",
        "input_payload_sha256",
        "selected_last_game_frame",
        "spawn_calls",
        "initialized_bullets",
        "rank_call_counts",
        "zero_allocation_calls",
        "maximum_pre_call_active_slots",
        "expected_geometry_sha256",
        "expected_statement_sha256",
    ):
        assert workload[field] == report[field], field
    summary = SUMMARY.pack(
        workload["selected_last_game_frame"],
        workload["spawn_calls"],
        workload["initialized_bullets"],
        workload["rank_call_counts"]["1"],
        workload["rank_call_counts"]["2"],
        workload["rank_call_counts"]["3"],
        workload["zero_allocation_calls"],
        workload["maximum_pre_call_active_slots"],
        workload["character"],
        workload["shot_type"],
        workload["maximum_rank"],
        workload["profile_flags"],
        bytes.fromhex(workload["expected_geometry_sha256"]),
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    assert statement.hex() == workload["expected_statement_sha256"]
    assert manifest["public_values_audit"]["decoded_bytes"] == list(statement)
    assert manifest["public_values_audit"]["matches_expected_statement_sha256"] is True
    assert manifest["public_values_audit"]["one_bit_wrong_expected_digest_rejected"] is True

    meter = manifest["meter"]
    assert [row["spawn_calls"] for row in meter] == [1, 10, 100, 1_000, 1_590]
    assert all(row["instructions"] > 0 and row["cells"] > 0 for row in meter)
    assert meter[-1]["statement_sha256"] == workload["expected_statement_sha256"]
    assert manifest["verification"]["expected_executable_commit_accepted"] is True
    assert manifest["verification"]["one_bit_wrong_executable_commit_rejected"] is True
    assert manifest["verification"]["one_bit_wrong_public_digest_rejected"] is True
    assert "independently observed" in manifest["claim_boundary"]
    assert "not an enclosing" in manifest["claim_boundary"]

    lock_text = (ROOT / "zkvm" / "player-bullets-openvm" / "Cargo.lock").read_text(
        encoding="utf-8"
    )
    assert manifest["backend"]["cargo_openvm_revision"] in lock_text
    print("validated tracked OpenVM local Player bullet-spawn proof bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check the tracked enclosing-state OpenVM proof and all source bindings."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence"
MANIFEST = EVIDENCE_DIR / "openvm-player-state-1999-v1.json"
VECTOR = EVIDENCE_DIR / "player-state-002677-2000-v1.bin"
BUILDER = ROOT / "tools" / "build_player_state_openvm_input.py"
STATEMENT_DOMAIN = b"zkTH06/openvm/player-state/v1\0"
FINAL_STATE = struct.Struct("<IIIBB2xi")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["type"] == "zkth06.openvm-enclosing-player-state-proof"
    assert manifest["schema_version"] == 1
    assert manifest["backend"]["cargo_openvm_version"] == "2.0.1"
    assert manifest["backend"]["cargo_openvm_revision"].startswith("b820b25")
    assert manifest["backend"]["vm_extensions"] == ["rv32i", "rv32m", "io", "sha2"]

    workload = manifest["workload"]
    assert workload["source_vector_sha256"] == sha256(VECTOR)
    assert workload["source_vector_bytes"] == VECTOR.stat().st_size
    assert workload["profile"] == "full-speed-no-bomb-no-hit-no-time-stop-write"
    assert workload["transitions"] == 1_999
    assert workload["input_payload_bytes"] == 4_018
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

    with tempfile.TemporaryDirectory(prefix="zkth06-openvm-state-evidence-") as directory:
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

    for field in (
        "source_vector_sha256",
        "input_payload_bytes",
        "input_payload_sha256",
        "expected_final_game_frame",
        "expected_final_x_bits",
        "expected_final_y_bits",
        "expected_final_player_state",
        "expected_final_flags",
        "expected_final_invulnerability_timer",
        "expected_statement_sha256",
    ):
        assert workload[field] == report[field], field
    final_state = FINAL_STATE.pack(
        workload["expected_final_game_frame"],
        workload["expected_final_x_bits"],
        workload["expected_final_y_bits"],
        workload["expected_final_player_state"],
        workload["expected_final_flags"],
        workload["expected_final_invulnerability_timer"],
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + final_state).digest()
    assert statement.hex() == workload["expected_statement_sha256"]
    assert manifest["public_values_audit"]["decoded_bytes"] == list(statement)
    assert manifest["public_values_audit"]["matches_expected_statement_sha256"] is True
    assert manifest["public_values_audit"]["one_bit_wrong_expected_digest_rejected"] is True

    meter = manifest["meter"]
    assert [row["transitions"] for row in meter] == [1, 10, 100, 1_000, 1_999]
    assert all(row["instructions"] > 0 and row["cells"] > 0 for row in meter)
    assert meter[-1]["statement_sha256"] == workload["expected_statement_sha256"]
    assert manifest["verification"]["expected_executable_commit_accepted"] is True
    assert manifest["verification"]["one_bit_wrong_executable_commit_rejected"] is True

    iteration = manifest["design_iteration"]
    assert iteration["previous_environment_witness_payload_bytes"] == 95_976
    assert iteration["enclosing_state_payload_bytes"] == 4_018
    assert iteration["previous_environment_witness_cells"] == 254_156_116
    assert iteration["enclosing_state_cells"] == 209_865_030
    assert iteration["cell_reduction"] == 44_291_086
    assert "per-frame movement environment words are no longer witness-provided" in manifest[
        "claim_boundary"
    ]
    assert "not yet derived from registration" in manifest["claim_boundary"]

    lock_text = (ROOT / "zkvm" / "player-state-openvm" / "Cargo.lock").read_text(
        encoding="utf-8"
    )
    assert manifest["backend"]["cargo_openvm_revision"] in lock_text
    print("validated tracked OpenVM enclosing-player-state proof bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

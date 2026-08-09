#!/usr/bin/env python3
"""Validate the tracked, proprietary-byte-free ECL dispatch audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import ecl_var_dispatch_audit as dispatch  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "ecl-var-dispatch-v1.json"
LEDGER = ROOT / "arithmetic" / "obligations-v1.json"
EXPECTED_ARTIFACT_SHA256 = "4f30ab443aa0a557ed7d39c2389a8be329601eba956aed073f05bad51b46e4cc"


def reject_disassembly_operands(value: Any) -> None:
    if isinstance(value, dict):
        assert "operands" not in value
        for child in value.values():
            reject_disassembly_operands(child)
    elif isinstance(value, list):
        for child in value:
            reject_disassembly_operands(child)


def main() -> int:
    artifact_text = ARTIFACT.read_text()
    assert "/home/" not in artifact_text
    assert "local/original-th06" not in artifact_text
    document = json.loads(artifact_text)
    ledger = json.loads(LEDGER.read_text())

    assert document["schema_version"] == dispatch.SCHEMA_VERSION
    assert document["kind"] == dispatch.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"] == {
        "executable_sha256": arithmetic_obligations.PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": arithmetic_obligations.PINNED_MAPPING_SHA256,
        "base_ledger_artifact_sha256": ledger["artifact_sha256"],
    }
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "ecl_var_dispatch_audit.py"
    )
    assert document["generator"]["x87_audit_sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "x87_audit.py"
    )
    assert document["mapped_functions"] == [
        {
            "name": "th06::EnemyEclInstr::GetVar",
            "start": "0x0040afb0",
            "size": 0x36C,
        },
        {
            "name": "th06::EnemyEclInstr::GetVarFloat",
            "start": "0x0040b380",
            "size": 0x40,
        },
    ]
    assert document["critical_ftol2_obligation_id"] == "ftol2-0040b38b"

    contract = document["dispatch_contract"]
    assert contract["normalization_addend"] == 10025
    assert contract["maximum_unsigned_index"] == 24
    assert contract["first_variable_id"] == -10025
    assert contract["last_variable_id"] == -10001
    assert contract["jump_table_address"] == "0x0040b31c"
    table = contract["jump_table"]
    assert len(table) == 25
    assert [entry["normalized_index"] for entry in table] == list(range(25))
    assert [entry["variable_id"] for entry in table] == list(range(-10025, -10000))
    assert len({entry["target"] for entry in table}) == 25
    assert all(
        dispatch.GET_VAR_ADDRESS
        <= int(entry["target"], 16)
        < dispatch.GET_VAR_ADDRESS + dispatch.GET_VAR_SIZE
        for entry in table
    )

    checked = document["checked_instruction_roles"]
    assert len(checked) == len(dispatch.EXPECTED_INSTRUCTIONS) == 17
    assert [int(row["address"], 16) for row in checked] == list(
        dispatch.EXPECTED_INSTRUCTIONS
    )
    assert document["model_contracts"]["machine_interval_theorem"] == (
        "ZkTH06.EclVarId.machine_classifier_matches_signed_interval"
    )
    assert "not a decoder proof" in document["evidence_status"]
    assert len(document["open_obligations"]) == 4
    reject_disassembly_operands(document)
    print("validated 25-way GetVar dispatch and 17 checked instruction roles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

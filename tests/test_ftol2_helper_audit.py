#!/usr/bin/env python3
"""Validate the tracked, proprietary-byte-free __ftol2 helper-path audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import ftol2_helper_audit as audit  # noqa: E402
import run_ftol2_probe as probe  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "ftol2-helper-v1.json"
BASE_LEDGER = ROOT / "arithmetic" / "obligations-v1.json"
EXPECTED_ARTIFACT_SHA256 = "46c87767f9d864ebbb2eca60d698fdaa6f355674c51d231f510e369f77427153"


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
    base_ledger = json.loads(BASE_LEDGER.read_text())

    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"] == {
        "executable_sha256": probe.EXECUTABLE_SHA256,
        "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
    }
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "ftol2_helper_audit.py"
    )
    assert document["generator"]["run_ftol2_probe_sha256"] == (
        arithmetic_obligations.sha256_file(ROOT / "tools" / "run_ftol2_probe.py")
    )
    assert document["helper"] == {
        "address": "0x0045ba78",
        "size": 117,
        "sha256": probe.HELPER_SHA256,
        "entry": "one x87 value in ST(0)",
        "result": "signed 64-bit value split across EDX:EAX",
        "required_control_word": "0x027f",
    }

    invalid = document["masked_invalid_path"]
    assert invalid["stored_result"] == "0x8000000000000000"
    assert invalid["eax"] == "0x00000000"
    assert invalid["edx"] == "0x80000000"
    assert len(invalid["path"]) == 4
    assert "selects the top-score branch" in invalid["score_site_observation"]

    checked = document["checked_instruction_roles"]
    assert len(checked) == len(audit.EXPECTED_INSTRUCTIONS) == 37
    assert [int(row["address"], 16) for row in checked] == list(audit.EXPECTED_INSTRUCTIONS)
    assert document["counts"] == {
        "checked_instruction_roles": 37,
        "point_item_callers_using_eax": 8,
    }
    assert len(document["open_obligations"]) == 6
    assert document["model_contracts"]["observed_zero"] == (
        "ZkTH06.X87Ftol2.integer_indefinite_observed_low32_zero"
    )
    reject_disassembly_operands(document)
    print("validated 37 __ftol2 helper instructions and masked-invalid low-EAX path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

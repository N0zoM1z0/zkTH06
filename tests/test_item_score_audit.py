#!/usr/bin/env python3
"""Validate the tracked, proprietary-byte-free point-item score audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import item_score_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "item-score-v1.json"
BASE_LEDGER = ROOT / "arithmetic" / "obligations-v1.json"
SOURCE_LEDGER = ROOT / "arithmetic" / "ftol2-source-candidates-v1.json"
HELPER_AUDIT = ROOT / "arithmetic" / "ftol2-helper-v1.json"
EXPECTED_ARTIFACT_SHA256 = "25319fc8d8a188103111b64426844dfb0c4399dfc7f6849ac1f48bf45dc8d138"


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
    source_ledger = json.loads(SOURCE_LEDGER.read_text())
    helper_audit = json.loads(HELPER_AUDIT.read_text())

    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"] == {
        "executable_sha256": arithmetic_obligations.PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": arithmetic_obligations.PINNED_MAPPING_SHA256,
        "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
        "source_candidate_artifact_sha256": source_ledger["artifact_sha256"],
        "ftol2_helper_artifact_sha256": helper_audit["artifact_sha256"],
    }
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "item_score_audit.py"
    )
    assert document["generator"]["x87_audit_sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "x87_audit.py"
    )
    assert document["mapped_function"] == {
        "name": audit.FUNCTION_NAME,
        "start": "0x0041f4a0",
        "size": 0xC58,
    }
    assert document["field_contract"] == {
        "item_current_position_y_offset": 0x114,
        "load_width": "binary32",
        "first_and_second_load_are_same_field": True,
        "converted_result_projection": "signed EAX",
    }

    entries = document["difficulty_dispatch"]["entries"]
    assert [entry["difficulty_value"] for entry in entries] == list(range(5))
    assert [entry["difficulty_name"] for entry in entries] == [
        "easy",
        "normal",
        "hard",
        "lunatic",
        "extra",
    ]
    assert [entry["target"] for entry in entries] == [
        "0x0041fb0b",
        "0x0041fb0b",
        "0x0041fb88",
        "0x0041fc08",
        "0x0041fc85",
    ]

    profiles = document["score_contract"]["profiles"]
    assert [profile["name"] for profile in profiles] == [
        "easy-normal",
        "hard",
        "lunatic",
        "extra",
    ]
    assert [profile["top_score"] for profile in profiles] == [
        100000,
        150000,
        200000,
        300000,
    ]
    assert [profile["bottom_score"] for profile in profiles] == [
        60000,
        100000,
        150000,
        200000,
    ]
    assert [profile["position_multiplier"] for profile in profiles] == [100, 180, 270, 400]
    assert all(profile["threshold"] == 128 for profile in profiles)
    calls = [address for profile in profiles for address in profile["helper_call_addresses"]]
    assert calls == [
        "0x0041fb14",
        "0x0041fb35",
        "0x0041fb91",
        "0x0041fbb2",
        "0x0041fc11",
        "0x0041fc32",
        "0x0041fc8e",
        "0x0041fcaf",
    ]
    assert {
        obligation for profile in profiles for obligation in profile["base_obligation_ids"]
    } == {f"ftol2-{address[2:]}" for address in calls}

    checked = document["checked_instruction_roles"]
    assert len(checked) == len(audit.EXPECTED_INSTRUCTIONS) == 77
    assert [int(row["address"], 16) for row in checked] == list(audit.EXPECTED_INSTRUCTIONS)
    assert document["counts"] == {
        "difficulty_entries": 5,
        "score_profiles": 4,
        "ftol2_calls": 8,
        "checked_instruction_roles": 77,
    }
    assert "unordered-false on NaN" in document["critical_nan_note"]
    assert "low-EAX observation is zero" in document["critical_nan_note"]
    assert len(document["open_obligations"]) == 7
    assert document["model_contracts"]["bounded_score"] == (
        "ZkTH06.ItemPointScore.bounded_score_range"
    )
    assert document["model_contracts"]["total_coordinate_score"] == (
        "ZkTH06.ItemPointScore.collected_score_range_without_item_finiteness"
    )
    reject_disassembly_operands(document)
    print("validated four point-item score profiles, eight helper calls, and 77 instruction roles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

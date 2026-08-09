#!/usr/bin/env python3
"""Validate the tracked, proprietary-byte-free player-position audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import player_position_audit as audit  # noqa: E402
import x87_audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "player-position-v1.json"
BASE_LEDGER = ROOT / "arithmetic" / "obligations-v1.json"
EXPECTED_ARTIFACT_SHA256 = "9479136fa169191d88c96ef92f06607eeaeaa751996bab0fcd820f4a2a2440bb"


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
        "executable_sha256": arithmetic_obligations.PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": arithmetic_obligations.PINNED_MAPPING_SHA256,
        "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
    }
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "player_position_audit.py"
    )
    assert document["generator"]["x87_audit_sha256"] == x87_audit.sha256_file(
        ROOT / "tools" / "x87_audit.py"
    )
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["upstream"]["correspondence_status"].endswith("-unproved")

    assert document["counts"] == {
        "mapped_functions": 8,
        "source_anchors": 21,
        "binary32_constants": 5,
        "character_speed_records": 4,
        "checked_instruction_roles": 95,
        "comparison_contracts": 4,
    }
    checked = document["checked_instruction_roles"]
    assert len(checked) == len(audit.EXPECTED_INSTRUCTIONS) == 95
    assert [int(row["address"], 16) for row in checked] == list(audit.EXPECTED_INSTRUCTIONS)

    constants = {
        int(row["address"], 16): int(row["bits"], 16)
        for row in document["binary32_constants"]
    }
    assert constants == {
        address: expected[0] for address, expected in audit.BINARY32_CONSTANTS.items()
    }
    assert [row["binary32_bits"] for row in document["character_speed_table"]] == [
        [f"0x{bits:08x}" for bits in record]
        for record in audit.EXPECTED_CHARACTER_SPEEDS
    ]

    comparisons = {row["address"]: row for row in document["comparison_contracts"]}
    assert set(comparisons) == set(audit.REQUIRED_COMPARISONS)
    assert all(row["base_slice_disposition"] == "unclassified" for row in comparisons.values())
    assert comparisons["0x00427159"]["truth_table_theorem"].endswith(
        "and_4100_je_table"
    )
    assert comparisons["0x00427171"]["truth_table_theorem"].endswith(
        "test_5_jp_table"
    )

    derived = document["derived_contract"]
    assert derived["initial_and_respawn_y"] == "384"
    assert (derived["movement_lower_y"], derived["movement_upper_y"]) == ("16", "432")
    assert derived["grab_radius_y"] == "12"
    assert derived["ordered_clamp_exception_behavior"] == {
        "negative_infinity": "assign lower 16",
        "positive_infinity": "assign upper 432",
        "nan": "both JP branches skip assignment; NaN survives",
    }
    assert derived["lean_contracts"]["total_clamp"] == (
        "ZkTH06.PlayerPosition.clamp_bounded_of_not_nan"
    )
    assert len(document["open_obligations"]) == 8
    reject_disassembly_operands(document)
    print("validated 95 player-position instructions and total clamp contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

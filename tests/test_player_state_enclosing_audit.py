#!/usr/bin/env python3
"""Validate the proprietary-byte-free enclosing player-state audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import player_state_enclosing_audit as audit  # noqa: E402
import x87_audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "player-state-enclosing-v1.json"
PLAYER_POSITION = ROOT / "arithmetic" / "player-position-v1.json"
EXPECTED_ARTIFACT_SHA256 = "8e2e2504a94380ed37b0d5752aef62d1d14cb3de1d3f2d0f062e0c821077cc35"


def reject_disassembly_operands(value: Any) -> None:
    if isinstance(value, dict):
        assert "operands" not in value
        for child in value.values():
            reject_disassembly_operands(child)
    elif isinstance(value, list):
        for child in value:
            reject_disassembly_operands(child)


def main() -> int:
    artifact_text = ARTIFACT.read_text(encoding="utf-8")
    assert "/home/" not in artifact_text
    assert "local/original-th06" not in artifact_text
    document = json.loads(artifact_text)
    player_position = json.loads(PLAYER_POSITION.read_text(encoding="utf-8"))

    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"] == {
        "executable_sha256": arithmetic_obligations.PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": arithmetic_obligations.PINNED_MAPPING_SHA256,
        "player_position_artifact_sha256": player_position["artifact_sha256"],
    }
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "player_state_enclosing_audit.py"
    )
    assert document["generator"]["x87_audit_sha256"] == x87_audit.sha256_file(
        ROOT / "tools" / "x87_audit.py"
    )
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["upstream"]["correspondence_status"].endswith("-unproved")
    assert document["counts"] == {
        "mapped_functions": 5,
        "source_anchors": 30,
        "checked_instruction_roles": 55,
    }
    checked = document["checked_instruction_roles"]
    assert len(checked) == len(audit.EXPECTED_INSTRUCTIONS) == 55
    assert [int(row["address"], 16) for row in checked] == list(audit.EXPECTED_INSTRUCTIONS)

    contract = document["derived_profile_contract"]
    assert contract["profile"] == "full-speed-no-bomb-no-hit-no-time-stop-write"
    assert contract["anchor"] == {
        "game_frame": 1,
        "player_state": 3,
        "invulnerability_timer": 239,
        "timer_subframe_bits": "0x00000000",
        "bomb_active": 0,
        "position_x_bits": "0x43400000",
        "position_y_bits": "0x43c00000",
    }
    assert contract["full_speed_rate_bits"] == "0x3f800000"
    assert contract["inactive_bomb_multiplier_bits"] == "0x3f800000"
    assert contract["fixed_motion_contract_artifact_sha256"] == player_position[
        "artifact_sha256"
    ]
    assert len(contract["unsupported_writers_fail_closed"]) == 4
    assert len(document["open_obligations"]) == 5
    reject_disassembly_operands(document)
    print("validated 55 enclosing-state instructions and the closed transition profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

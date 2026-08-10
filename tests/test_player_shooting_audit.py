#!/usr/bin/env python3
"""Validate the proprietary-byte-free shooting-cadence audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import player_shooting_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "player-shooting-v1.json"
ENCLOSING = ROOT / "arithmetic" / "player-state-enclosing-v1.json"
EXPECTED_ARTIFACT_SHA256 = "77bc7c34e69964494abad1ca5968af0756f43b9e619b4118df041d08ee946b83"


def reject_operands(value: Any) -> None:
    if isinstance(value, dict):
        assert "operands" not in value
        for child in value.values():
            reject_operands(child)
    elif isinstance(value, list):
        for child in value:
            reject_operands(child)


def main() -> int:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "/home/" not in text
    assert "local/original-th06" not in text
    document = json.loads(text)
    enclosing = json.loads(ENCLOSING.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    assert document["inputs"]["enclosing_player_state_artifact_sha256"] == enclosing["artifact_sha256"]
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["counts"] == {
        "mapped_functions": len(audit.MAPPED_FUNCTIONS),
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "checked_instruction_roles": len(audit.EXPECTED_INSTRUCTIONS),
    }
    contract = document["derived_profile_contract"]
    assert contract["shoot_input_mask"] == "0x0001"
    assert contract["focus_input_mask"] == "0x0004"
    assert contract["timer_start"]["current"] == 0
    assert contract["inactive_timer"] == {"previous": -999, "current": -1}
    assert "callback geometry" in contract["refinement_boundary"]
    assert len(document["open_obligations"]) == 5
    reject_operands(document)
    print(
        f"validated {len(audit.EXPECTED_INSTRUCTIONS)} shooting instructions "
        "through the callback boundary"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

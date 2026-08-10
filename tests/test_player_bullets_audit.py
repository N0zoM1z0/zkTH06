#!/usr/bin/env python3
"""Validate the proprietary-byte-free Player bullet-spawn audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import player_bullets_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "player-bullets-v1.json"
SHOOTING = ROOT / "arithmetic" / "player-shooting-v1.json"
EXPECTED_ARTIFACT_SHA256 = "055bb1c0ceee0e464a6dc1208a357d824d136ed1c9ba3b54696229ea09969ba2"


def reject_operands(value: Any) -> None:
    if isinstance(value, dict):
        assert "operands" not in value
        for child in value.values():
            reject_operands(child)
    elif isinstance(value, list):
        for child in value:
            reject_operands(child)


def main() -> int:
    artifact_text = ARTIFACT.read_text(encoding="utf-8")
    assert "/home/" not in artifact_text
    document = json.loads(artifact_text)
    shooting = json.loads(SHOOTING.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    assert document["inputs"]["player_shooting_artifact_sha256"] == shooting["artifact_sha256"]
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["counts"] == {
        "mapped_functions": len(audit.MAPPED_FUNCTIONS),
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "checked_instruction_roles": len(audit.EXPECTED_INSTRUCTIONS),
    }
    contract = document["derived_profile_contract"]
    assert contract["route"] == "Reimu A"
    assert contract["slot_count"] == 80
    assert contract["rank_thresholds"] == [8, 16, 32]
    assert contract["supported_power"] == {"minimum": 0, "maximum": 31, "ranks": [1, 2, 3]}
    assert len(contract["nonlaser_carried_fields"]) == 4
    assert "no host libm equivalence" in contract["trigonometry_boundary"]
    assert "no cross-call linkage" in contract["refinement_boundary"]
    assert len(document["open_obligations"]) == 5
    reject_operands(document)
    print(
        f"validated {len(audit.EXPECTED_INSTRUCTIONS)} Player bullet-spawn instructions "
        "through the local allocation/geometry boundary"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

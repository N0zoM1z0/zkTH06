#!/usr/bin/env python3
"""Validate the proprietary-byte-free early Enemy collision audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import early_enemy_collision_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "early-enemy-collision-v1.json"
LIFECYCLE = ROOT / "arithmetic" / "player-bullet-lifecycle-v1.json"
EXPECTED_ARTIFACT_SHA256 = "3724a636ca2c8751127683caf5314a2b3fe5ce6cc4fc00d11cc489b1ffbd6640"


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
    document = json.loads(text)
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    assert document["inputs"]["stage1_ecl_sha256"] == audit.STAGE1_ECL_SHA256
    assert document["inputs"]["player_bullet_lifecycle_artifact_sha256"] == lifecycle[
        "artifact_sha256"
    ]
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["counts"] == {
        "mapped_functions": len(audit.MAPPED_FUNCTIONS),
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "checked_instruction_roles": len(audit.EXPECTED_INSTRUCTIONS),
        "timeline_spawns": 5,
    }
    profile = document["decoded_stage1_profile"]
    assert profile["timeline_times"] == [128, 144, 160, 176, 192]
    assert profile["post_calc_game_frames"] == [129, 145, 161, 177, 193]
    assert profile["hitbox_bits"] == ["0x41e00000", "0x41e00000", "0x42000000"]
    contract = document["derived_profile_contract"]
    assert contract["first_collision_game_frame"] == 208
    assert contract["collision_damage"] == 48
    assert contract["collision_slot"] == 2
    assert contract["post_collision_score"] == 390
    assert len(document["open_obligations"]) == 5
    reject_operands(document)
    print(
        f"validated {len(audit.EXPECTED_INSTRUCTIONS)} early Enemy-collision "
        "instructions and five fixed timeline spawns"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

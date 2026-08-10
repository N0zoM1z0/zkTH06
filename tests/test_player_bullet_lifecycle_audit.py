#!/usr/bin/env python3
"""Validate the proprietary-byte-free Player bullet-lifecycle audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import player_bullet_lifecycle_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "player-bullet-lifecycle-v1.json"
SPAWN = ROOT / "arithmetic" / "player-bullets-v1.json"
EXPECTED_ARTIFACT_SHA256 = "a82bbf8c40b449e4d2280e805e642a971be719dee970788f344eb8ee1feef5e4"


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
    spawn = json.loads(SPAWN.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == (
        arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    )
    assert document["inputs"]["player_bullet_spawn_artifact_sha256"] == spawn[
        "artifact_sha256"
    ]
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["writer_inventory"]["player_bullet_state_source_lines"] == [
        126,
        426,
        580,
        585,
        1073,
    ]
    assert document["counts"] == {
        "mapped_functions": len(audit.MAPPED_FUNCTIONS),
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "checked_instruction_roles": len(audit.EXPECTED_INSTRUCTIONS),
        "player_bullet_state_writers": len(audit.PLAYER_BULLET_STATE_WRITERS),
    }
    contract = document["derived_profile_contract"]
    assert contract["anchor_game_frame"] == 1
    assert contract["maximum_collision_free_game_frame"] == 207
    assert contract["first_external_collision_game_frame"] == 208
    assert contract["straight_sprite_size_bits"] == ["0x41600000", "0x41600000"]
    assert "overwrites x, y, and z" in contract["draw_noninterference"]
    assert len(document["open_obligations"]) == 5
    reject_operands(document)
    print(
        f"validated {len(audit.EXPECTED_INSTRUCTIONS)} Player bullet-lifecycle "
        "instructions and the five-writer inventory"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

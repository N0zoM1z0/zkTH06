#!/usr/bin/env python3
"""Validate the proprietary-byte-free complete first-wave audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import first_wave_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "first-wave-v1.json"
LIFECYCLE = ROOT / "arithmetic" / "player-bullet-lifecycle-v1.json"
EARLY = ROOT / "arithmetic" / "early-enemy-collision-v1.json"
EXPECTED_ARTIFACT_SHA256 = "dc8c91a7cc64e49c63308f0f8ca4775ae698724ae6eb40679b96d9d2c5e87521"


def main() -> int:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "/home/" not in text
    document = json.loads(text)
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    early = json.loads(EARLY.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    assert document["inputs"]["player_bullet_lifecycle_artifact_sha256"] == lifecycle["artifact_sha256"]
    assert document["inputs"]["early_enemy_collision_artifact_sha256"] == early["artifact_sha256"]
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["counts"] == {
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "enemy_deaths": 5,
        "incremental_transitions": 21,
    }
    contract = document["derived_profile_contract"]
    assert contract["enemy_death_game_frames"] == [208, 213, 219, 224, 229]
    assert contract["collision_slots"] == [2, 3, 4, 0, 1]
    assert contract["post_wave_score"] == 1950
    assert contract["post_wave_active_enemies"] == 0
    assert contract["post_wave_collided_bullets"] == 5
    assert contract["collision_anm"]["first_observed_exit_game_frame"] == 238
    assert "frame 249" in contract["finite_prefix_noninterference"]["items"]
    assert len(document["open_obligations"]) == 5
    print("validated complete first-wave finite-prefix audit and item feedback boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

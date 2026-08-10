#!/usr/bin/env python3
"""Validate the proprietary-byte-free second-wave audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import second_wave_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "second-wave-v1.json"
FIRST_ITEM = ROOT / "arithmetic" / "first-item-v1.json"
EXPECTED_ARTIFACT_SHA256 = "9e968608c356645fa0d4694211f6f11ab2a0c712994eb6dce0e0949bef219b8a"


def main() -> int:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "/home/" not in text
    document = json.loads(text)
    first_item = json.loads(FIRST_ITEM.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    assert document["inputs"]["first_item_artifact_sha256"] == first_item["artifact_sha256"]
    assert document["upstream"]["revision"] == audit.player_position_audit.UPSTREAM_REVISION
    assert document["counts"] == {
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "incremental_transitions": 101,
        "enemy_deaths": 5,
    }
    contract = document["derived_profile_contract"]
    assert contract["last_game_frame"] == 350
    assert contract["timeline_spawns"] == [257, 273, 289, 305, 321, 337]
    assert contract["second_group_deaths"] == [328, 331, 335, 343, 350]
    assert contract["death_effect_rng_u16_calls"] == [55, 25, 25, 55, 25]
    assert contract["rng_anchor"] == {"seed": 41015, "generation": 157}
    assert contract["rng_final"] == {"seed": 37443, "generation": 342}
    assert contract["enemy_bullets"]["active_slots"] == 0
    assert len(document["open_obligations"]) == 3
    print("validated second-wave Enemy/ECL, Item-drop, RNG, and empty Enemy-bullet audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

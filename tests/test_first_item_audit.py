#!/usr/bin/env python3
"""Validate the proprietary-byte-free first Item feedback audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import first_item_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "first-item-v1.json"
FIRST_WAVE = ROOT / "arithmetic" / "first-wave-v1.json"
ITEM_SCORE = ROOT / "arithmetic" / "item-score-v1.json"
EXPECTED_ARTIFACT_SHA256 = "1dcc3f77e38f695def1535760bc15e813e98dda899f039c938a1f92c8a19416b"


def main() -> int:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "/home/" not in text
    document = json.loads(text)
    first_wave = json.loads(FIRST_WAVE.read_text(encoding="utf-8"))
    item_score = json.loads(ITEM_SCORE.read_text(encoding="utf-8"))
    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"]["executable_sha256"] == arithmetic_obligations.PINNED_EXECUTABLE_SHA256
    assert document["inputs"]["first_wave_artifact_sha256"] == first_wave["artifact_sha256"]
    assert document["inputs"]["item_score_artifact_sha256"] == item_score["artifact_sha256"]
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION
    assert document["counts"] == {
        "source_anchors": len(audit.SOURCE_ANCHORS),
        "incremental_transitions": 41,
        "spawned_items": 1,
        "collected_items": 1,
    }
    contract = document["derived_profile_contract"]
    assert contract["last_game_frame"] == 249
    assert contract["spawn"]["game_frame"] == 219
    assert contract["spawn"]["item_type"] == "ITEM_POWER_SMALL"
    assert contract["collection"] == {
        "game_frame": 249,
        "power_after": 1,
        "power_before": 0,
        "score_after": 1960,
        "score_before": 1950,
        "subrank_after": 1,
        "subrank_before": 0,
    }
    assert contract["collision_anm_reclamation_frames"] == [238, 243, 249]
    assert len(document["open_obligations"]) == 4
    print("validated first Item spawn, motion, AABB collection, and feedback audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

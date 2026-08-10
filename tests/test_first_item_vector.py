#!/usr/bin/env python3
"""Validate the first Item-feedback vector and provenance."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import build_first_item_vector as builder  # noqa: E402


VECTOR = ROOT / "evidence" / "first-item-002677-249-v1.bin"
MANIFEST = ROOT / "evidence" / "first-item-002677-249-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-300-items-v1.json"
AUDIT = ROOT / "arithmetic" / "first-item-v1.json"
PARENT = ROOT / "evidence" / "first-wave-002677-229-v1.bin"
EXPECTED_VECTOR_SHA256 = "2454c98c1ee1b0595db14758de40a9604918a45351c8026edda6c9e1ab300ebb"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    texts = [path.read_text(encoding="utf-8") for path in (MANIFEST, COMPARISON, AUDIT)]
    assert "/home/" not in "".join(texts)
    manifest, comparison, audit = map(json.loads, texts)
    assert manifest["type"] == "zkth06.first-item-vector"
    assert manifest["vector_sha256"] == sha256(vector) == EXPECTED_VECTOR_SHA256
    assert manifest["vector_bytes"] == len(vector) == 140_484
    assert manifest["source_frames"] == 300
    assert manifest["selected_frames"] == 249
    assert manifest["tested_transitions"] == 248
    assert manifest["incremental_anchor_game_frame"] == 208
    assert manifest["metrics"] == {
        "collision_anm_reclamation_frames": [238, 243, 249],
        "final_active_bullets": 3,
        "final_collided_bullets": 2,
        "final_power": 1,
        "final_random_spawn_index": 6,
        "final_random_table_index": 1,
        "final_score": 1960,
        "final_subrank": 1,
        "item_collection_game_frame": 249,
        "item_spawn_game_frame": 219,
    }
    assert comparison["status"] == "match"
    assert comparison["comparison_profile"] == builder.COMPARISON_PROFILE
    assert comparison["compared_frames"] == 300
    assert comparison["observed_item_metrics"] == {
        "first_active_game_frame": 219,
        "first_collection_game_frame": 249,
        "maximum_active_items": 1,
    }
    bindings = manifest["bindings"]
    assert bindings["comparison_sha256"] == sha256(COMPARISON.read_bytes())
    assert bindings["static_audit_sha256"] == sha256(AUDIT.read_bytes())
    assert bindings["parent_first_wave_vector_sha256"] == sha256(PARENT.read_bytes())
    assert bindings["generator_sha256"] == sha256(
        (ROOT / "tools" / "build_first_item_vector.py").read_bytes()
    )
    assert arithmetic_obligations.document_digest(audit) == audit["artifact_sha256"]

    header = builder.HEADER.unpack_from(vector)
    assert header[0] == builder.MAGIC
    assert header[1:10] == (
        builder.SCHEMA_VERSION,
        builder.HEADER.size,
        builder.FRAME.size,
        builder.ENEMY.size,
        builder.BULLET.size,
        builder.ITEM.size,
        300,
        249,
        248,
    )
    assert header[10].hex() == bindings["retail_trace_sha256"]
    assert header[11].hex() == bindings["reference_trace_sha256"]
    assert header[12].hex() == bindings["comparison_sha256"]
    assert header[13].hex() == bindings["static_audit_sha256"]
    assert header[14].hex() == bindings["parent_first_wave_vector_sha256"]
    assert header[15].hex() == bindings["generator_sha256"]
    print("validated 248 linked transitions through first Item feedback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the canonical second-wave vector and provenance."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import build_second_wave_vector as builder  # noqa: E402


VECTOR = ROOT / "evidence" / "second-wave-002677-350-v1.bin"
MANIFEST = ROOT / "evidence" / "second-wave-002677-350-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-1200-enemy-bullets-v1.json"
AUDIT = ROOT / "arithmetic" / "second-wave-v1.json"
PARENT = ROOT / "evidence" / "first-item-002677-249-v1.bin"
EXPECTED_VECTOR_SHA256 = "97d974b1e7b6ff28dc56a0c7c40c9fb2d9d0f5c7ea10a0116fd7800327005fc6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    texts = [path.read_text(encoding="utf-8") for path in (MANIFEST, COMPARISON, AUDIT)]
    assert "/home/" not in "".join(texts)
    manifest, comparison, audit = map(json.loads, texts)
    assert manifest["type"] == "zkth06.second-wave-vector"
    assert manifest["vector_sha256"] == sha256(VECTOR) == EXPECTED_VECTOR_SHA256
    assert manifest["vector_bytes"] == len(vector) == 47_360
    assert manifest["source_frames"] == 1200
    assert manifest["input_frames"] == 350
    assert manifest["first_record_game_frame"] == 250
    assert manifest["incremental_transitions"] == 101
    assert manifest["last_game_frame"] == 350
    assert manifest["metrics"] == {
        "enemy_bullet_active_frames": 0,
        "enemy_deaths": [328, 331, 335, 343, 350],
        "final_active_enemies": 1,
        "final_active_items": 2,
        "final_rng_generation": 342,
        "final_rng_seed": 37443,
        "final_score": 3910,
        "timeline_spawns": [257, 273, 289, 305, 321, 337],
    }
    assert comparison["status"] == "match"
    assert comparison["comparison_profile"] == "enemy-bullets"
    assert comparison["compared_frames"] == 1200
    assert comparison["observed_enemy_bullet_metrics"] == {
        "final_active_bullets": 7,
        "first_active_game_frame": 1180,
        "maximum_active_bullets": 7,
    }
    bindings = manifest["bindings"]
    assert bindings["comparison_sha256"] == sha256(COMPARISON)
    assert bindings["audit_sha256"] == sha256(AUDIT)
    assert bindings["parent_vector_sha256"] == sha256(PARENT)
    assert bindings["builder_sha256"] == sha256(ROOT / "tools" / "build_second_wave_vector.py")
    assert arithmetic_obligations.document_digest(audit) == audit["artifact_sha256"]

    header = builder.HEADER.unpack_from(vector)
    assert header[0] == builder.MAGIC
    assert header[1:11] == (
        builder.SCHEMA_VERSION,
        builder.HEADER.size,
        builder.FRAME.size,
        builder.ENEMY.size,
        builder.BULLET.size,
        builder.ITEM.size,
        350,
        250,
        101,
        350,
    )
    assert header[11].hex() == bindings["retail_trace_sha256"]
    assert header[12].hex() == bindings["reference_trace_sha256"]
    assert header[13].hex() == bindings["comparison_sha256"]
    assert header[14].hex() == bindings["audit_sha256"]
    assert header[15].hex() == bindings["parent_vector_sha256"]
    assert header[16].hex() == bindings["builder_sha256"]
    print("validated 101 second-wave transitions and the 1200-frame Enemy-bullet oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

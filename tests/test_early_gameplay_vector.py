#!/usr/bin/env python3
"""Validate the linked early-gameplay vector and provenance."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import build_early_gameplay_vector as builder  # noqa: E402


VECTOR = ROOT / "evidence" / "early-gameplay-002677-208-v1.bin"
MANIFEST = ROOT / "evidence" / "early-gameplay-002677-208-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-225-enemy-collisions-v1.json"
AUDIT = ROOT / "arithmetic" / "early-enemy-collision-v1.json"
EXPECTED_VECTOR_SHA256 = "c98b3ff3d90ba0f972f0691ffcd2d76573d1e6677d1ec75ed7a5ae59473feb3a"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    comparison_text = COMPARISON.read_text(encoding="utf-8")
    audit_text = AUDIT.read_text(encoding="utf-8")
    assert "/home/" not in manifest_text + comparison_text + audit_text
    manifest = json.loads(manifest_text)
    comparison = json.loads(comparison_text)
    audit = json.loads(audit_text)
    assert manifest["type"] == "zkth06.early-gameplay-vector"
    assert manifest["vector_sha256"] == EXPECTED_VECTOR_SHA256
    assert sha256(vector) == EXPECTED_VECTOR_SHA256
    assert manifest["selected_frames"] == 208
    assert manifest["tested_transitions"] == 207
    assert manifest["first_damage_call_game_frame"] == 137
    assert manifest["first_collision_game_frame"] == 208
    assert manifest["damage_calls"] == 200
    assert manifest["damaging_calls"] == 1
    assert manifest["maximum_active_enemies"] == 5
    assert comparison["status"] == "match"
    assert comparison["comparison_profile"] == builder.COMPARISON_PROFILE
    assert comparison["compared_frames"] == 225
    assert len(comparison["compared_fields"]) == 53
    assert comparison["observed_enemy_collision_metrics"] == {
        "damage_calls": 249,
        "damaging_calls": 4,
        "first_damaging_game_frame": 208,
        "maximum_active_enemies": 5,
        "trace_overflow_frames": 0,
    }
    assert manifest["comparison_sha256"] == sha256(COMPARISON.read_bytes())
    assert manifest["static_audit_sha256"] == sha256(AUDIT.read_bytes())
    assert arithmetic_obligations.document_digest(audit) == audit["artifact_sha256"]
    assert manifest["static_audit_sealed_digest"] == audit["artifact_sha256"]
    assert manifest["generator"]["sha256"] == sha256(
        (ROOT / manifest["generator"]["path"]).read_bytes()
    )

    header = builder.HEADER.unpack_from(vector)
    assert header[0] == builder.MAGIC
    assert header[1:8] == (
        builder.SCHEMA_VERSION,
        builder.HEADER.size,
        builder.FRAME.size,
        builder.ENEMY.size,
        225,
        208,
        207,
    )
    assert header[8].hex() == manifest["retail_trace_sha256"]
    assert header[9].hex() == manifest["reference_trace_sha256"]
    assert header[10].hex() == manifest["comparison_sha256"]
    assert header[11].hex() == manifest["static_audit_sha256"]
    assert header[12].hex() == manifest["stage1_ecl_sha256"]
    assert header[13].hex() == manifest["generator"]["sha256"]
    assert len(vector) == 14_780
    print("validated 207 linked Player/early-Enemy transitions through the frame-208 hit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the linked Player bullet-lifecycle vector and provenance."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import build_player_bullet_lifecycle_vector as builder  # noqa: E402


VECTOR = ROOT / "evidence" / "player-bullet-lifecycle-002677-207-v1.bin"
MANIFEST = ROOT / "evidence" / "player-bullet-lifecycle-002677-207-v1.json"
COMPARISON = (
    ROOT / "evidence" / "retail-reference-002677-2000-player-bullet-lifecycle-v1.json"
)
AUDIT = ROOT / "arithmetic" / "player-bullet-lifecycle-v1.json"
EXPECTED_VECTOR_SHA256 = "eda255f59426c4d05ed328d098870e9b6b8a2ebeb675d7cf86145328827e248b"


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
    assert manifest["type"] == "zkth06.player-bullet-lifecycle-vector"
    assert manifest["vector_sha256"] == EXPECTED_VECTOR_SHA256
    assert sha256(vector) == EXPECTED_VECTOR_SHA256
    assert manifest["selected_frames"] == 207
    assert manifest["tested_transitions"] == 206
    assert manifest["first_external_collision_game_frame"] == 208
    assert manifest["spawn_calls"] == 173
    assert manifest["initialized_bullets"] == 35
    assert manifest["update_reclamations"] == 30
    assert manifest["maximum_active_slots"] == 7
    assert manifest["nondefault_target_frames"] == 70
    assert comparison["status"] == "match"
    assert comparison["comparison_profile"] == builder.COMPARISON_PROFILE
    assert comparison["compared_frames"] == 2_000
    assert len(comparison["compared_fields"]) == 50
    assert comparison["semantic_projection_exclusions"] == [
        {
            "observed_differences": 3898,
            "path": builder.DRAW_ONLY_PATH,
            "reason": (
                "DrawBulletExplosions writes 0.4 to collided sprite.pos.z after the "
                "post-calc anchor; UpdatePlayerBullets overwrites all sprite.pos "
                "components from gameplay position before bounds or ANM can read them"
            ),
        }
    ]
    assert manifest["comparison_sha256"] == sha256(COMPARISON.read_bytes())
    assert manifest["static_audit_sha256"] == sha256(AUDIT.read_bytes())
    assert arithmetic_obligations.document_digest(audit) == audit["artifact_sha256"]
    assert manifest["static_audit_sealed_digest"] == audit["artifact_sha256"]
    assert manifest["generator"]["sha256"] == sha256(
        (ROOT / manifest["generator"]["path"]).read_bytes()
    )

    header = builder.HEADER.unpack_from(vector)
    assert header[0] == builder.MAGIC
    assert header[1:7] == (
        builder.SCHEMA_VERSION,
        builder.HEADER.size,
        builder.FRAME.size,
        builder.BULLET.size,
        2_000,
        207,
    )
    assert header[7:11] == (0, 0, builder.PROFILE_FLAGS, 0)
    assert header[11:15] == (1, 207, 208, 7)
    assert header[15].hex() == manifest["retail_trace_sha256"]
    assert header[16].hex() == manifest["reference_trace_sha256"]
    assert header[17].hex() == manifest["comparison_sha256"]
    assert header[18].hex() == manifest["static_audit_sha256"]
    assert header[19].hex() == manifest["generator"]["sha256"]
    assert vector[builder.HEADER.size - 20 : builder.HEADER.size] == bytes(20)
    assert len(vector) == 101_904
    print("validated 206 linked Player/bullet lifecycle transitions through frame 207")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

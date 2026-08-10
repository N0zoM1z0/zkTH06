#!/usr/bin/env python3
"""Validate the complete first-wave vector and provenance."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import build_first_wave_vector as builder  # noqa: E402


VECTOR = ROOT / "evidence" / "first-wave-002677-229-v1.bin"
MANIFEST = ROOT / "evidence" / "first-wave-002677-229-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-260-enemy-collisions-v2.json"
AUDIT = ROOT / "arithmetic" / "first-wave-v1.json"
PARENT = ROOT / "evidence" / "early-gameplay-002677-208-v1.bin"
EXPECTED_VECTOR_SHA256 = "b645bc3e25dd9fcc8ec1cce29cd4971d522b70e48e69243842c3a2b5500cbbf3"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    texts = [path.read_text(encoding="utf-8") for path in (MANIFEST, COMPARISON, AUDIT)]
    assert "/home/" not in "".join(texts)
    manifest, comparison, audit = map(json.loads, texts)
    assert manifest["type"] == "zkth06.first-wave-vector"
    assert manifest["vector_sha256"] == sha256(vector) == EXPECTED_VECTOR_SHA256
    assert manifest["vector_bytes"] == len(vector) == 122_580
    assert manifest["source_frames"] == 260
    assert manifest["selected_frames"] == 229
    assert manifest["tested_transitions"] == 228
    assert manifest["incremental_anchor_game_frame"] == 208
    assert manifest["metrics"] == {
        "collisions": [[208, 2], [213, 3], [219, 4], [224, 0], [229, 1]],
        "damage_calls": 253,
        "damaging_calls": 5,
        "final_collided_bullets": 5,
        "final_rng_generation": 157,
        "final_score": 1950,
    }
    assert comparison["status"] == "match"
    assert comparison["comparison_profile"] == builder.COMPARISON_PROFILE
    assert comparison["compared_frames"] == 260
    bindings = manifest["bindings"]
    assert bindings["comparison_sha256"] == sha256(COMPARISON.read_bytes())
    assert bindings["static_audit_sha256"] == sha256(AUDIT.read_bytes())
    assert bindings["parent_early_gameplay_vector_sha256"] == sha256(PARENT.read_bytes())
    assert bindings["generator_sha256"] == sha256((ROOT / "tools" / "build_first_wave_vector.py").read_bytes())
    assert arithmetic_obligations.document_digest(audit) == audit["artifact_sha256"]

    header = builder.HEADER.unpack_from(vector)
    assert header[0] == builder.MAGIC
    assert header[1:9] == (
        builder.SCHEMA_VERSION,
        builder.HEADER.size,
        builder.FRAME.size,
        builder.ENEMY.size,
        builder.BULLET.size,
        260,
        229,
        228,
    )
    assert header[9].hex() == bindings["retail_trace_sha256"]
    assert header[10].hex() == bindings["reference_trace_sha256"]
    assert header[11].hex() == bindings["comparison_sha256"]
    assert header[12].hex() == bindings["static_audit_sha256"]
    assert header[13].hex() == bindings["parent_early_gameplay_vector_sha256"]
    assert header[14].hex() == bindings["generator_sha256"]
    print("validated 228 linked transitions through all five first-wave deaths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

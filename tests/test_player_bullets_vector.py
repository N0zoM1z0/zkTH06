#!/usr/bin/env python3
"""Validate the retail-bound Player bullet-spawn vector and bindings."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-bullets-002677-2000-v1.bin"
MANIFEST = ROOT / "evidence" / "player-bullets-002677-2000-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-2000-player-bullets-v1.json"
AUDIT = ROOT / "arithmetic" / "player-bullets-v1.json"
HEADER = struct.Struct("<8s6I4B2I32s32s32s32s32s20x")
PREFIX = struct.Struct("<IH4B9I80B2x")
ALLOCATION = struct.Struct("<4BhH12IiIi2h")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert "/home/" not in manifest_text
    assert manifest["type"] == "zkth06.player-bullet-spawn-vector"
    assert manifest["source_frames"] == 2_000
    assert manifest["spawn_calls"] == 1_590
    assert manifest["initialized_bullets"] == 422
    assert manifest["vector_sha256"] == sha256(vector)
    assert manifest["comparison_sha256"] == sha256(COMPARISON.read_bytes())
    assert manifest["static_audit_sha256"] == sha256(AUDIT.read_bytes())
    generator = ROOT / manifest["generator"]["path"]
    assert manifest["generator"]["sha256"] == sha256(generator.read_bytes())

    unpacked = HEADER.unpack_from(vector)
    (
        magic,
        schema,
        header_bytes,
        record_bytes,
        source_frames,
        spawn_calls,
        initialized_bullets,
        character,
        shot_type,
        maximum_rank,
        profile_flags,
        first_frame,
        last_frame,
        retail_hash,
        reference_hash,
        comparison_hash,
        audit_hash,
        generator_hash,
    ) = unpacked
    assert magic == b"ZKPBV1\0\0"
    assert schema == 1
    assert header_bytes == HEADER.size == 224
    assert record_bytes == PREFIX.size + 4 * ALLOCATION.size == 416
    assert (source_frames, spawn_calls, initialized_bullets) == (2_000, 1_590, 422)
    assert (character, shot_type, maximum_rank, profile_flags) == (0, 0, 3, 1)
    assert (first_frame, last_frame) == (35, 1_869)
    assert retail_hash.hex() == manifest["retail_trace_sha256"]
    assert reference_hash.hex() == manifest["reference_trace_sha256"]
    assert comparison_hash.hex() == manifest["comparison_sha256"]
    assert audit_hash.hex() == manifest["static_audit_sha256"]
    assert generator_hash.hex() == manifest["generator"]["sha256"]
    assert len(vector) == header_bytes + spawn_calls * record_bytes

    allocation_total = 0
    zero_calls = 0
    rank_calls = [0, 0, 0]
    previous_frame = 0
    maximum_active = 0
    for record_index in range(spawn_calls):
        offset = header_bytes + record_index * record_bytes
        prefix = PREFIX.unpack_from(vector, offset)
        game_frame, power, timer, focus, allocation_count, reserved, *tail = prefix
        positions, states = tail[:9], tail[9:]
        assert game_frame > previous_frame
        previous_frame = game_frame
        assert 0 <= timer < 30 and focus in (0, 1) and reserved == 0
        assert power < 32 and len(positions) == 9
        assert len(states) == 80 and all(state in (0, 1, 2) for state in states)
        assert allocation_count <= 4
        maximum_active = max(maximum_active, sum(state != 0 for state in states))
        rank_calls[0 if power < 8 else 1 if power < 16 else 2] += 1
        allocation_total += allocation_count
        zero_calls += allocation_count == 0
        allocation_offset = offset + PREFIX.size
        allocated_slots = []
        for allocation_index in range(4):
            blob = vector[
                allocation_offset + allocation_index * ALLOCATION.size :
                allocation_offset + (allocation_index + 1) * ALLOCATION.size
            ]
            if allocation_index < allocation_count:
                allocation = ALLOCATION.unpack(blob)
                allocated_slots.append(allocation[0])
                assert states[allocation[0]] == 0
            else:
                assert not any(blob)
        assert allocated_slots == sorted(allocated_slots)

    assert allocation_total == 422
    assert zero_calls == 1_272
    assert rank_calls == [953, 324, 313]
    assert maximum_active == manifest["maximum_pre_call_active_slots"] == 24
    assert "not linked across calls" in manifest["claim_boundary"]
    print("validated 1,590 local SpawnBullets calls and 422 initialized bullets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

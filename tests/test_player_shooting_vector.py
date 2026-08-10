#!/usr/bin/env python3
"""Validate the retail-bound shooting vector and source bindings."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-shooting-002677-2000-v1.bin"
MANIFEST = ROOT / "evidence" / "player-shooting-002677-2000-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-2000-shooting-v1.json"
AUDIT = ROOT / "arithmetic" / "player-shooting-v1.json"
HEADER = struct.Struct("<8sIIII4BI32s32s32s32s32s")
RECORD = struct.Struct("<IHBBiIIHBBii")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    comparison_bytes = COMPARISON.read_bytes()
    audit_bytes = AUDIT.read_bytes()
    assert "/home/" not in manifest_text
    assert manifest["type"] == "zkth06.player-shooting-state-vector"
    assert manifest["profile"] == "full-speed-no-dialogue-no-bomb-no-hit-no-time-stop-write"
    assert manifest["source_frames"] == 2_000
    assert manifest["tested_transitions"] == 1_999
    assert manifest["tested_spawn_calls"] > 0
    assert manifest["vector_sha256"] == sha256(vector)
    assert manifest["comparison_sha256"] == sha256(comparison_bytes)
    assert manifest["static_audit_sha256"] == sha256(audit_bytes)
    generator = ROOT / manifest["generator"]["path"]
    assert manifest["generator"]["sha256"] == sha256(generator.read_bytes())

    unpacked = HEADER.unpack_from(vector)
    (
        magic,
        schema,
        header_bytes,
        record_bytes,
        source_frames,
        character,
        shot_type,
        profile_flags,
        reserved,
        anchor_game_frame,
        target_hash,
        replay_hash,
        retail_trace_hash,
        comparison_hash,
        audit_hash,
    ) = unpacked
    assert magic == b"ZKSHV1\0\0"
    assert schema == 1
    assert header_bytes == HEADER.size == 192
    assert record_bytes == RECORD.size == 32
    assert source_frames == 2_000
    assert (character, shot_type, profile_flags, reserved, anchor_game_frame) == (0, 0, 0, 0, 1)
    assert target_hash.hex() == manifest["target_executable_sha256"]
    assert replay_hash.hex() == manifest["replay_sha256"]
    assert retail_trace_hash.hex() == manifest["retail_trace_sha256"]
    assert comparison_hash.hex() == manifest["comparison_sha256"]
    assert audit_hash.hex() == manifest["static_audit_sha256"]
    assert len(vector) == HEADER.size + source_frames * RECORD.size

    spawn_calls = 0
    previous = None
    for index in range(source_frames):
        record = RECORD.unpack_from(vector, HEADER.size + index * RECORD.size)
        (
            frame_index,
            input_mask,
            player_state,
            flags,
            invulnerability_timer,
            x_bits,
            y_bits,
            previous_input,
            spawn_timer,
            record_reserved,
            fire_previous,
            fire_current,
        ) = record
        assert frame_index == index
        assert input_mask & 0x0002 == 0
        assert flags & 0x0B == 0
        assert record_reserved == 0
        if index == 0:
            assert (
                player_state,
                flags,
                invulnerability_timer,
                x_bits,
                y_bits,
                previous_input,
                spawn_timer,
                fire_previous,
                fire_current,
            ) == (3, 0, 239, 0x43400000, 0x43C00000, 0, 0xFF, -999, -1)
        else:
            assert previous_input == input_mask
            assert bool(flags & 4) == bool(input_mask & 4)
            expected_fire_previous = previous[10]
            expected_fire_current = previous[11]
            if expected_fire_current < 0 and input_mask & 1:
                expected_fire_previous, expected_fire_current = -999, 0
            expected_spawn = 0xFF
            if expected_fire_current >= 0:
                if expected_fire_current != expected_fire_previous:
                    expected_spawn = expected_fire_current
                expected_fire_previous = expected_fire_current
                expected_fire_current += 1
                if expected_fire_current >= 30:
                    expected_fire_previous, expected_fire_current = -999, -1
            assert spawn_timer == expected_spawn
            assert (fire_previous, fire_current) == (
                expected_fire_previous,
                expected_fire_current,
            )
            if spawn_timer != 0xFF:
                assert 0 <= spawn_timer < 30
                spawn_calls += 1
        previous = record
    assert spawn_calls == manifest["tested_spawn_calls"]
    assert manifest["final_state"]["spawn_call_count"] == spawn_calls
    print(f"validated 1,999 shooting transitions and {spawn_calls} callback requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

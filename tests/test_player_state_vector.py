#!/usr/bin/env python3
"""Validate the tracked closed player-state vector and its source bindings."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-state-002677-2000-v1.bin"
MANIFEST = ROOT / "evidence" / "player-state-002677-2000-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-2000-enclosing-v1.json"
HEADER = struct.Struct("<8sIIII4BI32s32s32s32s")
RECORD = struct.Struct("<IHBBiII")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    vector = VECTOR.read_bytes()
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    comparison_bytes = COMPARISON.read_bytes()
    comparison = json.loads(comparison_bytes)

    assert "/home/" not in manifest_text
    assert manifest["type"] == "zkth06.enclosing-player-state-vector"
    assert manifest["profile"] == "full-speed-no-bomb-no-hit-no-time-stop-write"
    assert manifest["source_frames"] == 2_000
    assert manifest["tested_transitions"] == 1_999
    assert manifest["vector_sha256"] == sha256(vector)
    assert manifest["comparison_sha256"] == sha256(comparison_bytes)
    generator = ROOT / manifest["generator"]["path"]
    assert manifest["generator"]["sha256"] == sha256(generator.read_bytes())
    assert comparison["status"] == "match"
    assert comparison["comparison_profile"] == "enclosing-player"
    assert comparison["compared_frames"] == 2_000
    assert len(comparison["compared_fields"]) == 40

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
    ) = HEADER.unpack_from(vector)
    assert magic == b"ZKPSV1\0\0"
    assert schema == 1
    assert header_bytes == HEADER.size == 160
    assert record_bytes == RECORD.size == 20
    assert source_frames == 2_000
    assert (character, shot_type, profile_flags, reserved, anchor_game_frame) == (0, 0, 0, 0, 1)
    assert target_hash.hex() == manifest["target_executable_sha256"]
    assert replay_hash.hex() == manifest["replay_sha256"]
    assert retail_trace_hash.hex() == manifest["retail_trace_sha256"]
    assert comparison_hash.hex() == manifest["comparison_sha256"]
    assert len(vector) == HEADER.size + source_frames * RECORD.size

    previous_state = None
    previous_timer = None
    final = None
    for index in range(source_frames):
        record = RECORD.unpack_from(vector, HEADER.size + index * RECORD.size)
        frame_index, input_mask, state, flags, timer, x_bits, y_bits = record
        assert frame_index == index
        assert input_mask & 0x0002 == 0
        assert flags == 0
        if index == 0:
            assert (state, timer, x_bits, y_bits) == (
                3,
                239,
                0x43400000,
                0x43C00000,
            )
        elif previous_state == 3:
            expected_timer = previous_timer - 1
            assert (state, timer) == (0 if expected_timer == 0 else 3, expected_timer)
        else:
            assert (state, timer) == (0, previous_timer + 1)
        previous_state = state
        previous_timer = timer
        final = (frame_index + 1, state, timer, x_bits, y_bits)

    assert final is not None
    assert final == (
        manifest["final_state"]["game_frame"],
        manifest["final_state"]["player_state"],
        manifest["final_state"]["invulnerability_timer"],
        manifest["final_state"]["x_bits"],
        manifest["final_state"]["y_bits"],
    )
    print("validated closed player-state vector and 1,999-state recurrence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

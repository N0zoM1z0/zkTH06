#!/usr/bin/env python3
"""Build the closed player-state vector from an enclosing retail anchor."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


MAGIC = b"ZKPSV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8sIIII4BI32s32s32s32s")
RECORD = struct.Struct("<IHBBiII")
FRAME_TYPE = "zkth06.retail-anchor-frame"
HEADER_TYPE = "zkth06.retail-anchor-header"
PROFILE_FLAGS = 0  # full-speed, no bomb, no hit, no time-stop writer
ANCHOR_GAME_FRAME = 1
INPUT_BOMB = 0x0002

RAW_ENVIRONMENT = {
    "effective_rate_bits": 0x3F800000,
    "framerate_multiplier_bits": 0x3F800000,
    "movement_min_x_bits": 0x41000000,
    "movement_min_y_bits": 0x41800000,
    "movement_size_x_bits": 0x43B80000,
    "movement_size_y_bits": 0x43D00000,
    "horizontal_multiplier_bits": 0x3F800000,
    "vertical_multiplier_bits": 0x3F800000,
}
CHARACTER_MOTION = {
    0: {
        "orthogonal_speed_bits": 0x40800000,
        "orthogonal_focus_speed_bits": 0x40000000,
        "diagonal_speed_bits": 0x403504F3,
        "diagonal_focus_speed_bits": 0x3FB504F3,
    },
    1: {
        "orthogonal_speed_bits": 0x40A00000,
        "orthogonal_focus_speed_bits": 0x40200000,
        "diagonal_speed_bits": 0x40614213,
        "diagonal_focus_speed_bits": 0x3FE14213,
    },
}

REQUIRED_COMPARISON_FIELDS = {
    "character",
    "shot_type",
    "input",
    "deaths",
    "bombs_used",
    "is_time_stopped",
    "player_state",
    "player_x_bits",
    "player_y_bits",
    "player_bomb_is_in_use",
    "player_invulnerability_timer_previous",
    "player_invulnerability_timer_subframe_bits",
    "player_invulnerability_timer_current",
} | set(RAW_ENVIRONMENT) | set(CHARACTER_MOTION[0])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_u32(value: Any) -> int:
    parsed = int(value, 0) if isinstance(value, str) else int(value)
    if not 0 <= parsed <= 0xFFFF_FFFF:
        raise ValueError(f"raw value outside u32: {value!r}")
    return parsed


def read_trace(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    trace_bytes = path.read_bytes()
    rows = [json.loads(line) for line in trace_bytes.splitlines() if line.strip()]
    if not rows or rows[0].get("type") != HEADER_TYPE:
        raise ValueError("retail trace header is missing or invalid")
    frames = rows[1:]
    if len(frames) < 2:
        raise ValueError("at least two retail frames are required")
    for index, frame in enumerate(frames):
        if frame.get("type") != FRAME_TYPE or int(frame.get("index", -1)) != index:
            raise ValueError(f"invalid or non-contiguous retail frame at index {index}")
    return rows[0], frames, trace_bytes


def validate_fixed_profile(frames: list[dict[str, Any]]) -> tuple[int, int]:
    character = int(frames[0]["character"])
    shot_type = int(frames[0]["shot_type"])
    if character not in CHARACTER_MOTION:
        raise ValueError(f"unsupported character: {character}")
    if shot_type not in (0, 1):
        raise ValueError(f"unsupported shot type: {shot_type}")
    expected_environment = RAW_ENVIRONMENT | CHARACTER_MOTION[character]

    previous_state = 3
    previous_timer = 239
    for index, frame in enumerate(frames):
        if int(frame["game_frame"]) != index + ANCHOR_GAME_FRAME:
            raise ValueError(f"unexpected game frame at index {index}")
        if int(frame["character"]) != character or int(frame["shot_type"]) != shot_type:
            raise ValueError(f"route configuration changed at frame {index}")
        if int(frame["input"]) & INPUT_BOMB:
            raise ValueError(f"bomb input is outside the closed profile at frame {index}")
        if int(frame["is_time_stopped"]) != 0:
            raise ValueError(f"time stop is outside the closed profile at frame {index}")
        if int(frame["player_bomb_is_in_use"]) != 0:
            raise ValueError(f"active bomb is outside the closed profile at frame {index}")
        if int(frame["player_respawn_timer"]) != 6:
            raise ValueError(f"respawn timer left its post-spawn value at frame {index}")
        if int(frame["deaths"]) != 0 or int(frame["bombs_used"]) != 0:
            raise ValueError(f"hit/bomb side effect is outside the closed profile at frame {index}")
        if raw_u32(frame["player_invulnerability_timer_subframe_bits"]) != 0:
            raise ValueError(f"fractional timer is outside full-speed profile at frame {index}")
        for field, expected in expected_environment.items():
            if raw_u32(frame[field]) != expected:
                raise ValueError(
                    f"derived environment mismatch at frame {index}: {field}"
                )

        state = int(frame["player_state"])
        timer = int(frame["player_invulnerability_timer_current"])
        timer_previous = int(frame["player_invulnerability_timer_previous"])
        if index == 0:
            if (
                state != 3
                or timer != 239
                or timer_previous != -999
                or raw_u32(frame["player_x_bits"]) != 0x43400000
                or raw_u32(frame["player_y_bits"]) != 0x43C00000
            ):
                raise ValueError("retail anchor state does not match the fixed constructor")
        else:
            if previous_state == 3:
                expected_timer = previous_timer - 1
                expected_state = 0 if expected_timer == 0 else 3
                expected_previous = -999
            else:
                expected_timer = previous_timer + 1
                expected_state = 0
                expected_previous = previous_timer
            if (state, timer, timer_previous) != (
                expected_state,
                expected_timer,
                expected_previous,
            ):
                raise ValueError(f"player life-state recurrence mismatch at frame {index}")
        previous_state = state
        previous_timer = timer
    return character, shot_type


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trace_header, frames, trace_bytes = read_trace(args.retail_trace)
    trace_sha256 = sha256_bytes(trace_bytes)
    comparison_bytes = args.comparison.read_bytes()
    comparison = json.loads(comparison_bytes)
    if comparison.get("status") != "match":
        raise ValueError("retail/reference comparison did not match")
    if comparison.get("comparison_profile") != "enclosing-player":
        raise ValueError("comparison does not use the enclosing-player profile")
    if int(comparison.get("compared_frames", -1)) != len(frames):
        raise ValueError("comparison and retail trace frame counts differ")
    missing = REQUIRED_COMPARISON_FIELDS - set(comparison.get("compared_fields", ()))
    if missing:
        raise ValueError("comparison omits enclosing fields: " + ", ".join(sorted(missing)))
    if comparison.get("retail_trace_sha256") != trace_sha256:
        raise ValueError("comparison is not bound to the supplied retail trace")

    target_sha256 = str(trace_header["target_executable_sha256"])
    replay_sha256 = str(trace_header["replay_sha256"])
    if comparison.get("target_executable_sha256") != target_sha256:
        raise ValueError("comparison target differs from retail trace")
    if comparison.get("replay_sha256") != replay_sha256:
        raise ValueError("comparison replay differs from retail trace")

    character, shot_type = validate_fixed_profile(frames)
    comparison_sha256 = sha256_bytes(comparison_bytes)
    vector = bytearray(
        HEADER.pack(
            MAGIC,
            SCHEMA_VERSION,
            HEADER.size,
            RECORD.size,
            len(frames),
            character,
            shot_type,
            PROFILE_FLAGS,
            0,
            ANCHOR_GAME_FRAME,
            bytes.fromhex(target_sha256),
            bytes.fromhex(replay_sha256),
            bytes.fromhex(trace_sha256),
            bytes.fromhex(comparison_sha256),
        )
    )
    for frame in frames:
        flags = int(bool(int(frame["is_time_stopped"]))) | (
            int(bool(int(frame["player_bomb_is_in_use"]))) << 1
        )
        vector.extend(
            RECORD.pack(
                int(frame["index"]),
                int(frame["input"]),
                int(frame["player_state"]),
                flags,
                int(frame["player_invulnerability_timer_current"]),
                raw_u32(frame["player_x_bits"]),
                raw_u32(frame["player_y_bits"]),
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    final = frames[-1]
    manifest = {
        "type": "zkth06.enclosing-player-state-vector",
        "schema_version": SCHEMA_VERSION,
        "format": "little-endian ZKPSV1",
        "header_bytes": HEADER.size,
        "record_bytes": RECORD.size,
        "source_frames": len(frames),
        "tested_transitions": len(frames) - 1,
        "anchor_game_frame": ANCHOR_GAME_FRAME,
        "last_game_frame": int(final["game_frame"]),
        "character": character,
        "shot_type": shot_type,
        "profile": "full-speed-no-bomb-no-hit-no-time-stop-write",
        "target_executable_sha256": target_sha256,
        "replay_sha256": replay_sha256,
        "retail_trace_sha256": trace_sha256,
        "reference_trace_sha256": comparison["reference_trace_sha256"],
        "comparison_artifact": args.comparison.name,
        "comparison_sha256": comparison_sha256,
        "vector_sha256": sha256_bytes(vector),
        "generator": {
            "path": "tools/build_player_state_vector.py",
            "sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
        },
        "initial_state": {
            "game_frame": 1,
            "player_state": 3,
            "invulnerability_timer": 239,
            "x_bits": 0x43400000,
            "y_bits": 0x43C00000,
        },
        "final_state": {
            "game_frame": int(final["game_frame"]),
            "player_state": int(final["player_state"]),
            "invulnerability_timer": int(final["player_invulnerability_timer_current"]),
            "x_bits": raw_u32(final["player_x_bits"]),
            "y_bits": raw_u32(final["player_y_bits"]),
        },
        "derived_environment": RAW_ENVIRONMENT | CHARACTER_MOTION[character],
        "claim_boundary": (
            "finite retail/reference evidence for a closed full-speed player-position/life-timer "
            "profile; excludes bomb, hit/death, respawn, and ECL time-stop writes and is not "
            "whole-player or whole-game equivalence"
        ),
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if "/home/" in manifest_text:
        raise AssertionError("manifest contains a local absolute path")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(manifest_text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "built",
                "source_frames": len(frames),
                "tested_transitions": len(frames) - 1,
                "vector_sha256": manifest["vector_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

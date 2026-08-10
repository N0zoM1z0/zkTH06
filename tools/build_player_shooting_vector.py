#!/usr/bin/env python3
"""Build a retail-bound vector for the closed Player shooting transition."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


MAGIC = b"ZKSHV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8sIIII4BI32s32s32s32s32s")
RECORD = struct.Struct("<IHBBiIIHBBii")
FRAME_TYPE = "zkth06.retail-anchor-frame"
HEADER_TYPE = "zkth06.retail-anchor-header"
PROFILE_FLAGS = 0
ANCHOR_GAME_FRAME = 1
INPUT_SHOOT = 0x0001
INPUT_BOMB = 0x0002
INPUT_FOCUS = 0x0004
NO_SPAWN = 0xFF

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
    "gui_has_current_message",
    "player_is_focus",
    "player_previous_frame_input",
    "player_fire_bullet_timer_previous",
    "player_fire_bullet_timer_subframe_bits",
    "player_fire_bullet_timer_current",
} | set(RAW_ENVIRONMENT) | set(CHARACTER_MOTION[0])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_u32(value: Any) -> int:
    parsed = int(value, 0) if isinstance(value, str) else int(value)
    if not 0 <= parsed <= 0xFFFF_FFFF:
        raise ValueError(f"raw value outside u32: {value!r}")
    return parsed


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    return json.loads(data), data


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


def life_step(previous_state: int, previous_timer: int) -> tuple[int, int, int]:
    if previous_state == 3:
        timer = previous_timer - 1
        return (0 if timer == 0 else 3, timer, -999)
    if previous_state == 0:
        return (0, previous_timer + 1, previous_timer)
    raise ValueError(f"unsupported preceding player state: {previous_state}")


def shooting_step(previous: dict[str, Any], frame: dict[str, Any]) -> int:
    timer_previous = int(previous["player_fire_bullet_timer_previous"])
    timer_current = int(previous["player_fire_bullet_timer_current"])
    input_mask = int(frame["input"])
    if timer_current < 0 and input_mask & INPUT_SHOOT:
        timer_previous = -999
        timer_current = 0

    spawn_timer = NO_SPAWN
    if timer_current >= 0:
        if timer_current != timer_previous:
            if not 0 <= timer_current < 30:
                raise ValueError(f"invalid callback timer: {timer_current}")
            spawn_timer = timer_current
        timer_previous = timer_current
        timer_current += 1
        if timer_current >= 30:
            timer_previous, timer_current = -999, -1

    observed = (
        int(frame["player_fire_bullet_timer_previous"]),
        int(frame["player_fire_bullet_timer_current"]),
    )
    if observed != (timer_previous, timer_current):
        raise ValueError(
            f"fire-timer recurrence mismatch at frame {frame['index']}: "
            f"expected {(timer_previous, timer_current)}, got {observed}"
        )
    return spawn_timer


def validate_profile(frames: list[dict[str, Any]]) -> tuple[int, int, list[int]]:
    character = int(frames[0]["character"])
    shot_type = int(frames[0]["shot_type"])
    if character not in CHARACTER_MOTION or shot_type not in (0, 1):
        raise ValueError("unsupported character/shot route")
    expected_environment = RAW_ENVIRONMENT | CHARACTER_MOTION[character]
    spawn_timers = [NO_SPAWN]

    first = frames[0]
    if (
        int(first["game_frame"]) != 1
        or int(first["player_state"]) != 3
        or int(first["player_invulnerability_timer_current"]) != 239
        or raw_u32(first["player_x_bits"]) != 0x43400000
        or raw_u32(first["player_y_bits"]) != 0x43C00000
        or int(first["player_is_focus"]) != 0
        or int(first["player_previous_frame_input"]) != 0
        or int(first["player_fire_bullet_timer_previous"]) != -999
        or int(first["player_fire_bullet_timer_current"]) != -1
    ):
        raise ValueError("retail trace does not begin at the fixed shooting anchor")

    for index, frame in enumerate(frames):
        if int(frame["game_frame"]) != index + ANCHOR_GAME_FRAME:
            raise ValueError(f"unexpected game frame at index {index}")
        if int(frame["character"]) != character or int(frame["shot_type"]) != shot_type:
            raise ValueError(f"route configuration changed at frame {index}")
        if int(frame["input"]) & INPUT_BOMB:
            raise ValueError(f"bomb input is outside the closed profile at frame {index}")
        if (
            int(frame["is_time_stopped"]) != 0
            or int(frame["player_bomb_is_in_use"]) != 0
            or int(frame["gui_has_current_message"]) != 0
        ):
            raise ValueError(f"dynamic gate left the closed profile at frame {index}")
        if int(frame["player_respawn_timer"]) != 6:
            raise ValueError(f"respawn timer left its post-spawn value at frame {index}")
        if int(frame["deaths"]) != 0 or int(frame["bombs_used"]) != 0:
            raise ValueError(f"hit/bomb side effect is outside the closed profile at frame {index}")
        if raw_u32(frame["player_invulnerability_timer_subframe_bits"]) != 0:
            raise ValueError(f"fractional life timer at frame {index}")
        if raw_u32(frame["player_fire_bullet_timer_subframe_bits"]) != 0:
            raise ValueError(f"fractional fire timer at frame {index}")
        for field, expected in expected_environment.items():
            if raw_u32(frame[field]) != expected:
                raise ValueError(f"derived environment mismatch at frame {index}: {field}")

        if index == 0:
            continue
        previous = frames[index - 1]
        expected_life = life_step(
            int(previous["player_state"]),
            int(previous["player_invulnerability_timer_current"]),
        )
        observed_life = (
            int(frame["player_state"]),
            int(frame["player_invulnerability_timer_current"]),
            int(frame["player_invulnerability_timer_previous"]),
        )
        if observed_life != expected_life:
            raise ValueError(f"life-state recurrence mismatch at frame {index}")
        if int(frame["player_is_focus"]) != int(bool(int(frame["input"]) & INPUT_FOCUS)):
            raise ValueError(f"focus recurrence mismatch at frame {index}")
        if int(frame["player_previous_frame_input"]) != int(frame["input"]):
            raise ValueError(f"previous-input recurrence mismatch at frame {index}")
        spawn_timers.append(shooting_step(previous, frame))
    return character, shot_type, spawn_timers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trace_header, frames, trace_bytes = read_trace(args.retail_trace)
    comparison, comparison_bytes = load_json(args.comparison)
    audit, audit_bytes = load_json(args.audit)
    trace_sha256 = sha256_bytes(trace_bytes)
    if comparison.get("status") != "match" or comparison.get("comparison_profile") != "player-shooting":
        raise ValueError("comparison is not a matched player-shooting profile")
    if int(comparison.get("compared_frames", -1)) != len(frames):
        raise ValueError("comparison and retail trace frame counts differ")
    missing = REQUIRED_COMPARISON_FIELDS - set(comparison.get("compared_fields", ()))
    if missing:
        raise ValueError("comparison omits shooting fields: " + ", ".join(sorted(missing)))
    if comparison.get("retail_trace_sha256") != trace_sha256:
        raise ValueError("comparison is not bound to the supplied retail trace")
    if audit.get("kind") != "zkth06.player-shooting-cadence-audit":
        raise ValueError("wrong static shooting audit kind")
    if audit.get("artifact_sha256") != sha256_bytes(
        json.dumps({k: v for k, v in audit.items() if k != "artifact_sha256"}, sort_keys=True, separators=(",", ":")).encode()
    ):
        raise ValueError("static shooting audit has an invalid sealed digest")

    target_sha256 = str(trace_header["target_executable_sha256"])
    replay_sha256 = str(trace_header["replay_sha256"])
    if comparison.get("target_executable_sha256") != target_sha256:
        raise ValueError("comparison target differs from retail trace")
    if comparison.get("replay_sha256") != replay_sha256:
        raise ValueError("comparison replay differs from retail trace")
    if audit.get("inputs", {}).get("executable_sha256") != target_sha256:
        raise ValueError("static audit target differs from retail trace")

    character, shot_type, spawn_timers = validate_profile(frames)
    comparison_sha256 = sha256_bytes(comparison_bytes)
    audit_sha256 = sha256_bytes(audit_bytes)
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
            bytes.fromhex(audit_sha256),
        )
    )
    for frame, spawn_timer in zip(frames, spawn_timers, strict=True):
        flags = (
            int(bool(int(frame["is_time_stopped"])))
            | (int(bool(int(frame["player_bomb_is_in_use"]))) << 1)
            | (int(bool(int(frame["player_is_focus"]))) << 2)
            | (int(bool(int(frame["gui_has_current_message"]))) << 3)
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
                int(frame["player_previous_frame_input"]),
                spawn_timer,
                0,
                int(frame["player_fire_bullet_timer_previous"]),
                int(frame["player_fire_bullet_timer_current"]),
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    final = frames[-1]
    spawn_calls = sum(value != NO_SPAWN for value in spawn_timers[1:])
    manifest = {
        "type": "zkth06.player-shooting-state-vector",
        "schema_version": SCHEMA_VERSION,
        "format": "little-endian ZKSHV1",
        "header_bytes": HEADER.size,
        "record_bytes": RECORD.size,
        "source_frames": len(frames),
        "tested_transitions": len(frames) - 1,
        "tested_spawn_calls": spawn_calls,
        "anchor_game_frame": ANCHOR_GAME_FRAME,
        "last_game_frame": int(final["game_frame"]),
        "character": character,
        "shot_type": shot_type,
        "profile": "full-speed-no-dialogue-no-bomb-no-hit-no-time-stop-write",
        "target_executable_sha256": target_sha256,
        "replay_sha256": replay_sha256,
        "retail_trace_sha256": trace_sha256,
        "reference_trace_sha256": comparison["reference_trace_sha256"],
        "comparison_artifact": args.comparison.name,
        "comparison_sha256": comparison_sha256,
        "static_audit_artifact": args.audit.name,
        "static_audit_sha256": audit_sha256,
        "static_audit_sealed_digest": audit["artifact_sha256"],
        "vector_sha256": sha256_bytes(vector),
        "generator": {
            "path": "tools/build_player_shooting_vector.py",
            "sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
        },
        "initial_state": {
            "game_frame": 1,
            "player_state": 3,
            "invulnerability_timer": 239,
            "x_bits": 0x43400000,
            "y_bits": 0x43C00000,
            "is_focus": 0,
            "previous_frame_input": 0,
            "fire_timer_previous": -999,
            "fire_timer_current": -1,
            "spawn_call_count": 0,
        },
        "final_state": {
            "game_frame": int(final["game_frame"]),
            "player_state": int(final["player_state"]),
            "invulnerability_timer": int(final["player_invulnerability_timer_current"]),
            "x_bits": raw_u32(final["player_x_bits"]),
            "y_bits": raw_u32(final["player_y_bits"]),
            "is_focus": int(final["player_is_focus"]),
            "previous_frame_input": int(final["player_previous_frame_input"]),
            "fire_timer_previous": int(final["player_fire_bullet_timer_previous"]),
            "fire_timer_current": int(final["player_fire_bullet_timer_current"]),
            "spawn_call_count": spawn_calls,
        },
        "claim_boundary": (
            "finite retail/reference evidence for position, life timer, focus, previous input, "
            "fire-timer cadence, and SpawnBullets call arguments; bullet-slot allocation and "
            "character callback geometry remain outside this vector"
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
                "tested_spawn_calls": spawn_calls,
                "vector_sha256": manifest["vector_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

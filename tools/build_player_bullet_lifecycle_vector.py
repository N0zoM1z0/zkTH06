#!/usr/bin/env python3
"""Build the collision-free enclosing Player/bullet lifecycle vector."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import arithmetic_obligations


MAGIC = b"ZKPLV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8s6I4B4I32s32s32s32s32s20x")
FRAME = struct.Struct("<IHBBiIIHBBiiIB3x")
BULLET = struct.Struct("<2Bh2h12IiIi3I2iI2H2I")
HEADER_TYPE = "zkth06.retail-anchor-header"
FRAME_TYPE = "zkth06.retail-anchor-frame"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
COMPARISON_PROFILE = "player-bullet-frames"
AUDIT_KIND = "zkth06.player-bullet-lifecycle-audit"
ANCHOR_GAME_FRAME = 1
LAST_GAME_FRAME = 207
FIRST_EXTERNAL_COLLISION_FRAME = 208
NO_SPAWN = 0xFF
PROFILE_FLAGS = 1  # fixed power 0, zero carry, straight/nonterminating ANM only
DRAW_ONLY_PATH = "player_bullet_update.before.active_slots[*].sprite_position_bits[2]"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_u32(value: Any) -> int:
    result = int(value, 0) if isinstance(value, str) else int(value)
    if not 0 <= result <= 0xFFFF_FFFF:
        raise ValueError(f"value outside raw u32: {value!r}")
    return result


def raw_vec(value: Any, count: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"expected {count}-element raw vector")
    return tuple(raw_u32(item) for item in value)


def read_retail(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    if not rows or rows[0].get("type") != HEADER_TYPE:
        raise ValueError("retail trace header is missing or invalid")
    frames = rows[1:]
    for index, frame in enumerate(frames):
        if frame.get("type") != FRAME_TYPE or int(frame.get("index", -1)) != index:
            raise ValueError(f"invalid retail frame at index {index}")
    return rows[0], frames, data


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    return json.loads(data), data


def stage_before_enemy(frame: dict[str, Any]) -> dict[str, Any]:
    spawn = frame["player_spawn"]
    return (spawn if spawn is not None else frame["player_bullet_update"])["after"]


def require_zero_carry(side: dict[str, Any], frame: int) -> None:
    carry = side.get("slot_carry")
    if not isinstance(carry, list) or len(carry) != 80:
        raise ValueError(f"missing 80-slot carry at frame {frame}")
    keys = ("sideways_motion_bits", "unk_134_x_bits", "unk_152", "spawn_position_idx")
    for slot, value in enumerate(carry):
        if any(raw_u32(value[key]) != 0 for key in keys):
            raise ValueError(f"nonzero carry at frame {frame}, slot {slot}")


def validate_active(bullet: dict[str, Any], frame: int) -> None:
    expected = {
        "state": 1,
        "type": 0,
        "damage": 48,
        "spawn_position_idx": 0,
        "unk_152": 0,
        "position_z": 0x3EFD70A4,
        "size": (0x41400000, 0x41400000, 0x3F800000),
        "velocity": (0xB50CCDE2, 0xC1400000),
        "sideways": 0,
        "unk_134": (0, 0x41400000, 0xBFC90FDB),
        "sprite_flags": 0x1003,
        "sprite_active": 1088,
        "sprite_file": 1088,
        "sprite_size": (0x41600000, 0x41600000),
    }
    observed = {
        "state": int(bullet["state"]),
        "type": int(bullet["type"]),
        "damage": int(bullet["damage"]),
        "spawn_position_idx": int(bullet["spawn_position_idx"]),
        "unk_152": int(bullet["unk_152"]),
        "position_z": raw_vec(bullet["position_bits"], 3)[2],
        "size": raw_vec(bullet["size_bits"], 3),
        "velocity": raw_vec(bullet["velocity_bits"], 2),
        "sideways": raw_u32(bullet["sideways_motion_bits"]),
        "unk_134": raw_vec(bullet["unk_134_bits"], 3),
        "sprite_flags": int(bullet["sprite_flags"]),
        "sprite_active": int(bullet["sprite_active_index"]),
        "sprite_file": int(bullet["sprite_anm_file_index"]),
        "sprite_size": raw_vec(bullet["sprite_size_bits"], 2),
    }
    if observed != expected:
        raise ValueError(f"active bullet left straight rank-1 profile at frame {frame}")
    if raw_vec(bullet["sprite_position_bits"], 3) != raw_vec(bullet["position_bits"], 3):
        raise ValueError(f"sprite/gameplay position mismatch at frame {frame}")
    age_previous = int(bullet["timer_previous"])
    age_current = int(bullet["timer_current"])
    age_valid = (age_previous, age_current) == (-999, 0) or (
        age_current > 0 and age_previous == age_current - 1
    )
    sprite_previous = int(bullet["sprite_timer_previous"])
    sprite_current = int(bullet["sprite_timer_current"])
    if (
        not age_valid
        or raw_u32(bullet["timer_subframe_bits"]) != 0
        or sprite_current <= 0
        or sprite_previous != sprite_current - 1
        or raw_u32(bullet["sprite_timer_subframe_bits"]) != 0
    ):
        raise ValueError(f"non-full-speed timer profile at frame {frame}")


def pack_bullet(value: dict[str, Any]) -> bytes:
    position = raw_vec(value["position_bits"], 3)
    size = raw_vec(value["size_bits"], 3)
    velocity = raw_vec(value["velocity_bits"], 2)
    unk_134 = raw_vec(value["unk_134_bits"], 3)
    sprite_position = raw_vec(value["sprite_position_bits"], 3)
    sprite_size = raw_vec(value["sprite_size_bits"], 2)
    return BULLET.pack(
        int(value["slot"]),
        int(value["type"]),
        int(value["damage"]),
        int(value["unk_152"]),
        int(value["spawn_position_idx"]),
        *position,
        *size,
        *velocity,
        raw_u32(value["sideways_motion_bits"]),
        *unk_134,
        int(value["timer_previous"]),
        raw_u32(value["timer_subframe_bits"]),
        int(value["timer_current"]),
        *sprite_position,
        int(value["sprite_timer_previous"]),
        int(value["sprite_timer_current"]),
        raw_u32(value["sprite_flags"]),
        int(value["sprite_active_index"]),
        int(value["sprite_anm_file_index"]),
        *sprite_size,
    )


def validate_profile(frames: list[dict[str, Any]]) -> dict[str, int]:
    if len(frames) < FIRST_EXTERNAL_COLLISION_FRAME:
        raise ValueError("trace is too short to establish the first collision boundary")
    first_external = next(
        (
            int(frame["game_frame"])
            for frame in frames
            if stage_before_enemy(frame) != frame["player_bullets_frame"]
        ),
        None,
    )
    if first_external != FIRST_EXTERNAL_COLLISION_FRAME:
        raise ValueError(f"unexpected first Enemy collision frame: {first_external}")
    selected = frames[:LAST_GAME_FRAME]
    if int(selected[0]["game_frame"]) != ANCHOR_GAME_FRAME:
        raise ValueError("wrong lifecycle anchor frame")
    if any(selected[0]["player_bullets_frame"]["slot_states"]):
        raise ValueError("frame-1 Player bullet pool is not empty")

    spawn_calls = 0
    initialized = 0
    reclaimed = 0
    maximum_active = 0
    nondefault_target_frames = 0
    for index, frame in enumerate(selected):
        game_frame = int(frame["game_frame"])
        if game_frame != index + ANCHOR_GAME_FRAME:
            raise ValueError(f"non-contiguous game frame {game_frame}")
        if (
            int(frame["character"]) != 0
            or int(frame["shot_type"]) != 0
            or int(frame["current_power"]) != 0
        ):
            raise ValueError(f"route/power left rank-1 Reimu A at frame {game_frame}")
        update = frame.get("player_bullet_update")
        if not isinstance(update, dict):
            raise ValueError(f"missing update event at frame {game_frame}")
        target = raw_vec(update["last_enemy_hit_bits"], 3)
        if target not in ((0, 0, 0), (0xC479C000, 0xC479C000, 0)):
            nondefault_target_frames += 1
        for side in (update["before"], update["after"], frame["player_bullets_frame"]):
            require_zero_carry(side, game_frame)
            for bullet in side["active_slots"]:
                validate_active(bullet, game_frame)
        if index and selected[index - 1]["player_bullets_frame"] != update["before"]:
            raise ValueError(f"cross-frame bullet boundary mismatch at frame {game_frame}")
        spawn = frame["player_spawn"]
        if spawn is not None:
            spawn_calls += 1
            if update["after"] != spawn["before"]:
                raise ValueError(f"update/spawn boundary mismatch at frame {game_frame}")
            initialized += sum(
                left == 0 and right == 1
                for left, right in zip(
                    spawn["before"]["slot_states"], spawn["after"]["slot_states"], strict=True
                )
            )
        if stage_before_enemy(frame) != frame["player_bullets_frame"]:
            raise ValueError(f"external bullet write inside selected prefix at frame {game_frame}")
        reclaimed += sum(
            left == 1 and right == 0
            for left, right in zip(
                update["before"]["slot_states"], update["after"]["slot_states"], strict=True
            )
        )
        maximum_active = max(maximum_active, len(frame["player_bullets_frame"]["active_slots"]))
    return {
        "spawn_calls": spawn_calls,
        "initialized_bullets": initialized,
        "update_reclamations": reclaimed,
        "maximum_active": maximum_active,
        "nondefault_target_frames": nondefault_target_frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    trace_header, frames, trace_bytes = read_retail(args.retail_trace)
    comparison, comparison_bytes = load_json(args.comparison)
    audit, audit_bytes = load_json(args.audit)
    if trace_header.get("target_executable_sha256") != TARGET_SHA256:
        raise ValueError("retail trace is bound to a different executable")
    if comparison.get("status") != "match" or comparison.get("comparison_profile") != COMPARISON_PROFILE:
        raise ValueError("comparison is not a matched lifecycle profile")
    if comparison.get("retail_trace_sha256") != sha256_bytes(trace_bytes):
        raise ValueError("comparison is bound to a different retail trace")
    exclusions = comparison.get("semantic_projection_exclusions")
    if (
        not isinstance(exclusions, list)
        or len(exclusions) != 1
        or exclusions[0].get("path") != DRAW_ONLY_PATH
        or int(exclusions[0].get("observed_differences", -1)) != 3898
    ):
        raise ValueError("unexpected lifecycle semantic projection")
    if audit.get("kind") != AUDIT_KIND:
        raise ValueError("wrong lifecycle audit kind")
    if arithmetic_obligations.document_digest(audit) != audit.get("artifact_sha256"):
        raise ValueError("lifecycle audit has an invalid sealed digest")
    if audit.get("inputs", {}).get("executable_sha256") != TARGET_SHA256:
        raise ValueError("lifecycle audit is bound to a different executable")

    metrics = validate_profile(frames)
    selected = frames[:LAST_GAME_FRAME]
    records = bytearray()
    for frame in selected:
        active = frame["player_bullets_frame"]["active_slots"]
        spawn = frame["player_spawn"]
        spawn_timer = NO_SPAWN if spawn is None else int(spawn["timer"])
        flags = (
            int(bool(int(frame["is_time_stopped"])))
            | (int(bool(int(frame["player_bomb_is_in_use"]))) << 1)
            | (int(bool(int(frame["player_is_focus"]))) << 2)
        )
        records.extend(
            FRAME.pack(
                int(frame["game_frame"]),
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
                sum(1 for prior in selected[: int(frame["game_frame"])] if prior["player_spawn"] is not None),
                len(active),
            )
        )
        for bullet in active:
            records.extend(pack_bullet(bullet))

    generator_hash = sha256_bytes(Path(__file__).resolve().read_bytes())
    vector_header = HEADER.pack(
        MAGIC,
        SCHEMA_VERSION,
        HEADER.size,
        FRAME.size,
        BULLET.size,
        len(frames),
        len(selected),
        0,
        0,
        PROFILE_FLAGS,
        0,
        ANCHOR_GAME_FRAME,
        LAST_GAME_FRAME,
        FIRST_EXTERNAL_COLLISION_FRAME,
        metrics["maximum_active"],
        bytes.fromhex(sha256_bytes(trace_bytes)),
        bytes.fromhex(comparison["reference_trace_sha256"]),
        bytes.fromhex(sha256_bytes(comparison_bytes)),
        bytes.fromhex(sha256_bytes(audit_bytes)),
        bytes.fromhex(generator_hash),
    )
    vector = vector_header + records
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    manifest = {
        "type": "zkth06.player-bullet-lifecycle-vector",
        "schema_version": SCHEMA_VERSION,
        "format": "little-endian ZKPLV1 variable active-slot records",
        "header_bytes": HEADER.size,
        "frame_prefix_bytes": FRAME.size,
        "active_bullet_bytes": BULLET.size,
        "source_frames": len(frames),
        "selected_frames": len(selected),
        "tested_transitions": len(selected) - 1,
        "anchor_game_frame": ANCHOR_GAME_FRAME,
        "last_game_frame": LAST_GAME_FRAME,
        "first_external_collision_game_frame": FIRST_EXTERNAL_COLLISION_FRAME,
        "character": 0,
        "shot_type": 0,
        "fixed_power": 0,
        "profile_flags": PROFILE_FLAGS,
        "spawn_calls": metrics["spawn_calls"],
        "initialized_bullets": metrics["initialized_bullets"],
        "update_reclamations": metrics["update_reclamations"],
        "maximum_active_slots": metrics["maximum_active"],
        "nondefault_target_frames": metrics["nondefault_target_frames"],
        "target_executable_sha256": TARGET_SHA256,
        "replay_sha256": trace_header.get("replay_sha256"),
        "retail_trace_sha256": sha256_bytes(trace_bytes),
        "reference_trace_sha256": comparison["reference_trace_sha256"],
        "comparison_artifact": args.comparison.name,
        "comparison_sha256": sha256_bytes(comparison_bytes),
        "static_audit_artifact": args.audit.name,
        "static_audit_sha256": sha256_bytes(audit_bytes),
        "static_audit_sealed_digest": audit["artifact_sha256"],
        "generator": {
            "path": "tools/build_player_bullet_lifecycle_vector.py",
            "sha256": generator_hash,
        },
        "vector_sha256": sha256_bytes(vector),
        "claim_boundary": (
            "finite collision-free Reimu-A rank-1 prefix from the fixed empty frame-1 pool through "
            "frame 207; every later slot pre-state is linked through update, bounds reclamation, and "
            "spawn, while Enemy collision first observed at frame 208 remains outside the transition"
        ),
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if "/home/" in text:
        raise AssertionError("manifest contains a local absolute path")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(text, encoding="utf-8")
    print(
        f"wrote {len(selected) - 1} linked transitions / {metrics['initialized_bullets']} bullets "
        f"({len(vector)} bytes, sha256={manifest['vector_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

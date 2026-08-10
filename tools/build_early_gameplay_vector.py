#!/usr/bin/env python3
"""Build the linked early-Stage-1 Enemy collision transition vector."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import arithmetic_obligations
import early_enemy_collision_audit


MAGIC = b"ZKEGP1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8s7I32s32s32s32s32s32s")
FRAME = struct.Struct("<IHBBI3I")
ENEMY = struct.Struct("<BBHii7I")
HEADER_KIND = "zkth06.retail-anchor-header"
FRAME_KIND = "zkth06.retail-anchor-frame"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
COMPARISON_PROFILE = "enemy-collisions"
ECL_SHA256 = "9d9a40e9f7e3ab9346d3874438134659cacf9d34f4aff57b96b4be4ea85b99d7"
ANCHOR_GAME_FRAME = 1
LAST_GAME_FRAME = 208
FIRST_DAMAGE_CALL_FRAME = 137
FIRST_COLLISION_FRAME = 208
NO_COLLISION = 0xFF
SPAWN_FRAMES = (129, 145, 161, 177, 193)
EXPECTED_HITBOX = (0x41E00000, 0x41E00000, 0x42000000)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_u32(value: Any) -> int:
    result = int(value, 0) if isinstance(value, str) else int(value)
    if not 0 <= result <= 0xFFFF_FFFF:
        raise ValueError(f"not a raw u32: {value!r}")
    return result


def raw_vec(value: Any, count: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"expected {count}-element raw vector")
    return tuple(raw_u32(item) for item in value)


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    return json.loads(data), data


def load_trace(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    if not rows or rows[0].get("type") != HEADER_KIND:
        raise ValueError("retail trace header is missing")
    frames = rows[1:]
    for index, frame in enumerate(frames):
        if frame.get("type") != FRAME_KIND or int(frame.get("index", -1)) != index:
            raise ValueError(f"invalid retail frame {index}")
    return rows[0], frames, data


def changed_slots(call: dict[str, Any]) -> list[int]:
    before = call["before"]["slot_states"]
    after = call["after"]["slot_states"]
    if len(before) != 80 or len(after) != 80:
        raise ValueError("damage call does not contain an 80-slot pool")
    return [slot for slot, (left, right) in enumerate(zip(before, after, strict=True)) if left != right]


def validate_profile(frames: list[dict[str, Any]]) -> dict[str, int]:
    if len(frames) < LAST_GAME_FRAME:
        raise ValueError("retail trace is shorter than the selected prefix")
    selected = frames[:LAST_GAME_FRAME]
    if [int(frame["game_frame"]) for frame in selected] != list(
        range(ANCHOR_GAME_FRAME, LAST_GAME_FRAME + 1)
    ):
        raise ValueError("selected game frames are not contiguous")
    if any(bool(frame.get("player_damage_trace_overflow")) for frame in selected):
        raise ValueError("Player damage trace overflowed")
    for frame in selected:
        game_frame = int(frame["game_frame"])
        if (
            int(frame["character"]) != 0
            or int(frame["shot_type"]) != 0
            or int(frame["current_power"]) != 0
            or int(frame["player_bomb_is_in_use"]) != 0
        ):
            raise ValueError(f"route left the fixed Reimu-A rank-1 profile at frame {game_frame}")
        expected_slots = [slot for slot, spawn in enumerate(SPAWN_FRAMES) if game_frame >= spawn]
        if game_frame >= FIRST_COLLISION_FRAME:
            expected_slots.remove(0)
        enemies = frame.get("enemies")
        if [int(enemy["slot"]) for enemy in enemies] != expected_slots:
            raise ValueError(f"unexpected early Enemy slots at frame {game_frame}")
        for enemy in enemies:
            if (
                raw_vec(enemy["hitbox_bits"], 3) != EXPECTED_HITBOX
                or int(enemy["ecl_sub"]) != 0
                or bool(enemy["boss"])
                or int(enemy["score"]) != 300
                or raw_vec(enemy["position_bits"], 3)[2] != 0
                or raw_vec(enemy["axis_speed_bits"], 3)[2] != 0
                or raw_u32(enemy["acceleration_bits"]) != 0
                or int(enemy["ecl_timer_previous"]) != int(enemy["ecl_time"]) - 1
                or raw_u32(enemy["ecl_timer_subframe_bits"]) != 0
            ):
                raise ValueError(f"Enemy left fixed Sub0 projection at frame {game_frame}")
    call_frames = [
        int(frame["game_frame"]) for frame in selected if frame.get("player_damage_calls")
    ]
    if not call_frames or call_frames[0] != FIRST_DAMAGE_CALL_FRAME:
        raise ValueError("unexpected first CalcDamageToEnemy frame")
    damaging = [
        (int(frame["game_frame"]), index, call)
        for frame in selected
        for index, call in enumerate(frame.get("player_damage_calls", []))
        if int(call["damage"]) != 0
    ]
    if len(damaging) != 1 or damaging[0][0:2] != (FIRST_COLLISION_FRAME, 0):
        raise ValueError("selected prefix does not contain the unique first collision")
    hit = damaging[0][2]
    if (
        int(hit["damage"]) != 48
        or changed_slots(hit) != [2]
        or int(hit["before"]["slot_states"][2]) != 1
        or int(hit["after"]["slot_states"][2]) != 2
    ):
        raise ValueError("first collision is not the fixed slot-2 straight-bullet hit")
    for frame in selected[:-1]:
        for call in frame.get("player_damage_calls", []):
            if call["before"] != call["after"]:
                raise ValueError("pre-boundary damage call mutated the Player pool")
    final = selected[-1]
    if (
        int(final["score"]) != 390
        or raw_vec(final["player_last_enemy_hit_bits"], 3)
        != raw_vec(hit["enemy_position_bits"], 3)
    ):
        raise ValueError("frame-208 score/target does not enclose the killed Enemy")
    return {
        "damage_calls": sum(len(frame.get("player_damage_calls", [])) for frame in selected),
        "damaging_calls": 1,
        "maximum_active_enemies": max(len(frame["enemies"]) for frame in selected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--ecl", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    header, frames, trace_bytes = load_trace(args.retail_trace)
    comparison, comparison_bytes = load_json(args.comparison)
    audit, audit_bytes = load_json(args.audit)
    ecl_bytes = args.ecl.read_bytes()
    if header.get("target_executable_sha256") != TARGET_SHA256:
        raise ValueError("retail trace is bound to a different executable")
    if comparison.get("status") != "match" or comparison.get("comparison_profile") != COMPARISON_PROFILE:
        raise ValueError("comparison is not a matched Enemy-collision profile")
    if comparison.get("retail_trace_sha256") != sha256_bytes(trace_bytes):
        raise ValueError("comparison is bound to another retail trace")
    if sha256_bytes(ecl_bytes) != ECL_SHA256:
        raise ValueError("Stage-1 ECL does not match the pinned profile")
    if (
        audit.get("kind") != early_enemy_collision_audit.KIND
        or arithmetic_obligations.document_digest(audit) != audit.get("artifact_sha256")
        or audit.get("inputs", {}).get("stage1_ecl_sha256") != ECL_SHA256
        or audit.get("inputs", {}).get("executable_sha256") != TARGET_SHA256
    ):
        raise ValueError("early Enemy-collision audit is invalid or bound to other inputs")
    metrics = validate_profile(frames)

    records = bytearray()
    for frame in frames[:LAST_GAME_FRAME]:
        enemies = frame["enemies"]
        collided = NO_COLLISION
        if int(frame["game_frame"]) == FIRST_COLLISION_FRAME:
            collided = 2
        records.extend(
            FRAME.pack(
                int(frame["game_frame"]),
                int(frame["input"]),
                len(enemies),
                collided,
                int(frame["score"]),
                *raw_vec(frame["player_last_enemy_hit_bits"], 3),
            )
        )
        for enemy in enemies:
            position = raw_vec(enemy["position_bits"], 3)
            axis = raw_vec(enemy["axis_speed_bits"], 3)
            flags = int(bool(int(enemy["flags"][1]) & 4))
            records.extend(
                ENEMY.pack(
                    int(enemy["slot"]),
                    flags,
                    0,
                    int(enemy["ecl_time"]),
                    int(enemy["life"]),
                    *position,
                    axis[0],
                    axis[1],
                    raw_u32(enemy["angle_bits"]),
                    raw_u32(enemy["angular_velocity_bits"]),
                )
            )

    generator_hash = sha256_bytes(Path(__file__).resolve().read_bytes())
    vector_header = HEADER.pack(
        MAGIC,
        SCHEMA_VERSION,
        HEADER.size,
        FRAME.size,
        ENEMY.size,
        len(frames),
        LAST_GAME_FRAME,
        LAST_GAME_FRAME - ANCHOR_GAME_FRAME,
        bytes.fromhex(sha256_bytes(trace_bytes)),
        bytes.fromhex(comparison["reference_trace_sha256"]),
        bytes.fromhex(sha256_bytes(comparison_bytes)),
        bytes.fromhex(sha256_bytes(audit_bytes)),
        bytes.fromhex(ECL_SHA256),
        bytes.fromhex(generator_hash),
    )
    vector = vector_header + records
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    manifest = {
        "type": "zkth06.early-gameplay-vector",
        "schema_version": SCHEMA_VERSION,
        "format": "little-endian ZKEGP1 variable Enemy records",
        "header_bytes": HEADER.size,
        "frame_prefix_bytes": FRAME.size,
        "enemy_bytes": ENEMY.size,
        "source_frames": len(frames),
        "selected_frames": LAST_GAME_FRAME,
        "tested_transitions": LAST_GAME_FRAME - ANCHOR_GAME_FRAME,
        "anchor_game_frame": ANCHOR_GAME_FRAME,
        "last_game_frame": LAST_GAME_FRAME,
        "first_damage_call_game_frame": FIRST_DAMAGE_CALL_FRAME,
        "first_collision_game_frame": FIRST_COLLISION_FRAME,
        "character": 0,
        "shot_type": 0,
        "fixed_power": 0,
        **metrics,
        "target_executable_sha256": TARGET_SHA256,
        "replay_sha256": header.get("replay_sha256"),
        "stage1_ecl_sha256": ECL_SHA256,
        "retail_trace_sha256": sha256_bytes(trace_bytes),
        "reference_trace_sha256": comparison["reference_trace_sha256"],
        "comparison_artifact": args.comparison.name,
        "comparison_sha256": sha256_bytes(comparison_bytes),
        "static_audit_artifact": args.audit.name,
        "static_audit_sha256": sha256_bytes(audit_bytes),
        "static_audit_sealed_digest": audit["artifact_sha256"],
        "generator": {
            "path": "tools/build_early_gameplay_vector.py",
            "sha256": generator_hash,
        },
        "vector_sha256": sha256_bytes(vector),
        "claim_boundary": (
            "fixed Reimu-A replay prefix through frame 208; five early Stage-1 Sub0 enemies, "
            "movement/ECL-time projection, damage AABB, first bullet collision, target, enemy "
            "death, and score are linked without per-frame Enemy or slot witnesses"
        ),
        "arithmetic_refinement_boundary": (
            "curved Sub0 axis-speed entries are a finite lookup indexed by derived ECL time and "
            "matched by both oracles; an x87 fsincos lookup/refinement proof remains open"
        ),
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if "/home/" in text:
        raise AssertionError("manifest contains a local absolute path")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(text, encoding="utf-8")
    print(
        f"wrote {manifest['tested_transitions']} linked transitions / "
        f"{metrics['damage_calls']} damage calls ({len(vector)} bytes, "
        f"sha256={manifest['vector_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

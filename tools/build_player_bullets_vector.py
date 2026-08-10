#!/usr/bin/env python3
"""Build the retail-bound Reimu-A SpawnBullets local-transition vector."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import arithmetic_obligations


MAGIC = b"ZKPBV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8s6I4B2I32s32s32s32s32s20x")
RECORD_PREFIX = struct.Struct("<IH4B9I80B2x")
ALLOCATION = struct.Struct("<4BhH12IiIi2h")
RECORD_BYTES = RECORD_PREFIX.size + 4 * ALLOCATION.size
HEADER_TYPE = "zkth06.retail-anchor-header"
FRAME_TYPE = "zkth06.retail-anchor-frame"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
PROFILE_FLAGS = 1  # all four non-laser carry fields are fixed zero in this vector
PLAYER_BULLET_ANM = 0x440
REIMU_A_ORB_BULLET_ANM = 0x441
Z_BITS = 0x3EFD70A4
ONE_BITS = 0x3F800000


STRAIGHT = {
    "wait": 5,
    "frame": 0,
    "motion": (0x00000000, 0x00000000),
    "size": (0x41400000, 0x41400000),
    "direction": 0xBFC90FDB,
    "speed": 0x41400000,
    "velocity": (0xB50CCDE2, 0xC1400000),
    "damage": 48,
    "source_spawn": 0,
    "type": 0,
    "anm": PLAYER_BULLET_ANM,
}
HOMING_LEFT = STRAIGHT | {
    "wait": 30,
    "direction": 0xC0060A92,
    "speed": 0x41200000,
    "velocity": (0xC0A00001, 0xC10A9066),
    "damage": 14,
    "source_spawn": 1,
    "type": 1,
    "anm": REIMU_A_ORB_BULLET_ANM,
}
HOMING_RIGHT = HOMING_LEFT | {
    "direction": 0xBF860A92,
    "velocity": (0x409FFFFF, 0xC10A9067),
    "source_spawn": 2,
}
SPREAD_LEFT = STRAIGHT | {
    "motion": (0xC0800000, 0),
    "direction": 0xBFCB4BC4,
    "velocity": (0xBE5674BA, 0xC13FF884),
    "damage": 30,
}
SPREAD_RIGHT = STRAIGHT | {
    "motion": (0x40800000, 0),
    "direction": 0xBFC6D3F2,
    "velocity": (0x3E567474, 0xC13FF884),
    "damage": 30,
}
RANKS = {
    1: (STRAIGHT,),
    2: (STRAIGHT, HOMING_LEFT, HOMING_RIGHT),
    3: (SPREAD_LEFT, SPREAD_RIGHT, HOMING_LEFT, HOMING_RIGHT),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def raw_u32(value: Any) -> int:
    parsed = int(value, 0) if isinstance(value, str) else int(value)
    if not 0 <= parsed <= 0xFFFF_FFFF:
        raise ValueError(f"raw value outside u32: {value!r}")
    return parsed


def raw_vec(values: Any, count: int) -> tuple[int, ...]:
    if not isinstance(values, list) or len(values) != count:
        raise ValueError(f"expected a {count}-element raw vector")
    return tuple(raw_u32(value) for value in values)


def f32_add(left_bits: int, right_bits: int) -> int:
    left = struct.unpack("<f", struct.pack("<I", left_bits))[0]
    right = struct.unpack("<f", struct.pack("<I", right_bits))[0]
    return struct.unpack("<I", struct.pack("<f", left + right))[0]


def rank_for_power(power: int) -> int:
    if 0 <= power < 8:
        return 1
    if power < 16:
        return 2
    if power < 32:
        return 3
    raise ValueError(f"power is outside the closed rank-1--3 profile: {power}")


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


def require_zero_carry(event: dict[str, Any], frame: int) -> None:
    keys = ("sideways_motion_bits", "unk_134_x_bits", "unk_152", "spawn_position_idx")
    for side_name in ("before", "after"):
        side = event[side_name]
        carry = side.get("slot_carry")
        if not isinstance(carry, list) or len(carry) != 80:
            raise ValueError(f"missing slot carry at frame {frame}")
        for slot, values in enumerate(carry):
            if any(raw_u32(values[key]) != 0 for key in keys):
                raise ValueError(f"nonzero dormant carry at frame {frame}, slot {slot}")
    if event["before"]["slot_carry"] != event["after"]["slot_carry"]:
        raise ValueError(f"SpawnBullets changed a carried field at frame {frame}")


def expected_allocations(event: dict[str, Any], frame: int) -> list[dict[str, Any]]:
    timer = int(event["timer"])
    power = int(event["current_power"])
    if not 0 <= timer < 30:
        raise ValueError(f"callback timer outside 0..29 at frame {frame}")
    before_states = [int(value) for value in event["before"]["slot_states"]]
    after_states = [int(value) for value in event["after"]["slot_states"]]
    if len(before_states) != 80 or len(after_states) != 80:
        raise ValueError(f"slot-state vector length mismatch at frame {frame}")
    if any(state not in (0, 1, 2) for state in before_states + after_states):
        raise ValueError(f"invalid slot state at frame {frame}")

    player_position = raw_vec(event["player_position_bits"], 3)
    orb_positions = tuple(raw_vec(value, 3) for value in event["orb_position_bits"])
    expected: list[dict[str, Any]] = []
    states = before_states.copy()
    next_slot = 0
    for data_index, bullet in enumerate(RANKS[rank_for_power(power)]):
        if timer % int(bullet["wait"]) != int(bullet["frame"]):
            continue
        slot = next((slot for slot in range(next_slot, 80) if states[slot] == 0), None)
        if slot is None:
            break
        next_slot = slot + 1
        states[slot] = 1
        source_index = int(bullet["source_spawn"])
        source = player_position if source_index == 0 else orb_positions[source_index - 1]
        motion = bullet["motion"]
        expected.append(
            {
                "slot": slot,
                "data_index": data_index,
                "type": int(bullet["type"]),
                "source_spawn": source_index,
                "damage": int(bullet["damage"]),
                "anm": int(bullet["anm"]),
                "position": (
                    f32_add(source[0], motion[0]),
                    f32_add(source[1], motion[1]),
                    Z_BITS,
                ),
                "size": (bullet["size"][0], bullet["size"][1], ONE_BITS),
                "velocity": bullet["velocity"],
                "sideways": 0,
                "unk134": (0, int(bullet["speed"]), int(bullet["direction"])),
                "timer_previous": -999,
                "timer_subframe": 0,
                "timer_current": 0,
                "unk152": 0,
                "stored_spawn": 0,
            }
        )
    if states != after_states:
        raise ValueError(f"slot allocation mismatch at frame {frame}")
    return expected


def validate_event(event: dict[str, Any], frame: int) -> list[dict[str, Any]]:
    require_zero_carry(event, frame)
    expected = expected_allocations(event, frame)
    before_active = {int(value["slot"]): value for value in event["before"]["active_slots"]}
    after_active = {int(value["slot"]): value for value in event["after"]["active_slots"]}
    for slot, value in before_active.items():
        if after_active.get(slot) != value:
            raise ValueError(f"existing active slot changed inside SpawnBullets at frame {frame}, slot {slot}")

    for allocation in expected:
        slot = allocation["slot"]
        observed = after_active.get(slot)
        if observed is None:
            raise ValueError(f"allocated slot missing at frame {frame}, slot {slot}")
        projection = {
            "type": int(observed["type"]),
            "source_spawn": allocation["source_spawn"],
            "damage": int(observed["damage"]),
            "anm": int(observed["sprite_anm_file_index"]),
            "position": raw_vec(observed["position_bits"], 3),
            "size": raw_vec(observed["size_bits"], 3),
            "velocity": raw_vec(observed["velocity_bits"], 2),
            "sideways": raw_u32(observed["sideways_motion_bits"]),
            "unk134": raw_vec(observed["unk_134_bits"], 3),
            "timer_previous": int(observed["timer_previous"]),
            "timer_subframe": raw_u32(observed["timer_subframe_bits"]),
            "timer_current": int(observed["timer_current"]),
            "unk152": int(observed["unk_152"]),
            "stored_spawn": int(observed["spawn_position_idx"]),
        }
        expected_projection = {key: allocation[key] for key in projection}
        if projection != expected_projection or int(observed["state"]) != 1:
            raise ValueError(f"initialized geometry mismatch at frame {frame}, slot {slot}")
        if (
            raw_vec(observed["sprite_position_bits"], 3) != allocation["position"]
            or int(observed["sprite_active_index"]) != allocation["anm"]
            or int(observed["sprite_anm_file_index"]) != allocation["anm"]
            or int(observed["sprite_flags"]) != 0x1003
            or int(observed["sprite_timer_previous"]) != 0
            or raw_u32(observed["sprite_timer_subframe_bits"]) != 0
            or int(observed["sprite_timer_current"]) != 1
        ):
            raise ValueError(f"ANM oracle projection mismatch at frame {frame}, slot {slot}")
    return expected


def pack_allocation(allocation: dict[str, Any] | None) -> bytes:
    if allocation is None:
        return bytes(ALLOCATION.size)
    return ALLOCATION.pack(
        allocation["slot"],
        allocation["data_index"],
        allocation["type"],
        allocation["source_spawn"],
        allocation["damage"],
        allocation["anm"],
        *allocation["position"],
        *allocation["size"],
        *allocation["velocity"],
        allocation["sideways"],
        *allocation["unk134"],
        allocation["timer_previous"],
        allocation["timer_subframe"],
        allocation["timer_current"],
        allocation["unk152"],
        allocation["stored_spawn"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    header, frames, retail_bytes = read_retail(args.retail_trace)
    comparison, comparison_bytes = load_json(args.comparison)
    audit, audit_bytes = load_json(args.audit)
    if header.get("target_executable_sha256") != TARGET_SHA256:
        raise ValueError("retail trace is bound to a different executable")
    if comparison.get("status") != "match" or comparison.get("comparison_profile") != "player-bullets":
        raise ValueError("comparison is not a matched player-bullets profile")
    if int(comparison.get("compared_frames", -1)) != len(frames):
        raise ValueError("comparison frame count does not bind the retail trace")
    if comparison.get("retail_trace_sha256") != sha256_bytes(retail_bytes):
        raise ValueError("comparison is bound to a different retail trace")
    if audit.get("kind") != "zkth06.player-bullet-spawn-audit":
        raise ValueError("wrong static bullet-spawn audit kind")
    if arithmetic_obligations.document_digest(audit) != audit.get("artifact_sha256"):
        raise ValueError("static bullet-spawn audit has an invalid digest")

    records: list[bytes] = []
    rank_calls = {1: 0, 2: 0, 3: 0}
    total_allocations = 0
    max_active = 0
    first_frame = 0
    last_frame = 0
    for frame_row in frames:
        event = frame_row.get("player_spawn")
        if event is None:
            continue
        game_frame = int(frame_row["game_frame"])
        allocations = validate_event(event, game_frame)
        states = tuple(int(value) for value in event["before"]["slot_states"])
        positions = raw_vec(event["player_position_bits"], 3) + tuple(
            component
            for orb in event["orb_position_bits"]
            for component in raw_vec(orb, 3)
        )
        rank_calls[rank_for_power(int(event["current_power"]))] += 1
        total_allocations += len(allocations)
        max_active = max(max_active, sum(state != 0 for state in states))
        first_frame = first_frame or game_frame
        last_frame = game_frame
        record = RECORD_PREFIX.pack(
            game_frame,
            int(event["current_power"]),
            int(event["timer"]),
            int(event["is_focus"]),
            len(allocations),
            0,
            *positions,
            *states,
        ) + b"".join(
            pack_allocation(allocations[index] if index < len(allocations) else None)
            for index in range(4)
        )
        if len(record) != RECORD_BYTES:
            raise AssertionError("internal player-bullet record size mismatch")
        records.append(record)

    generator_hash = sha256_file(Path(__file__).resolve())
    vector_header = HEADER.pack(
        MAGIC,
        SCHEMA_VERSION,
        HEADER.size,
        RECORD_BYTES,
        len(frames),
        len(records),
        total_allocations,
        int(frames[0]["character"]),
        int(frames[0]["shot_type"]),
        3,
        PROFILE_FLAGS,
        first_frame,
        last_frame,
        bytes.fromhex(sha256_bytes(retail_bytes)),
        bytes.fromhex(comparison.get("reference_trace_sha256")),
        bytes.fromhex(sha256_bytes(comparison_bytes)),
        bytes.fromhex(sha256_bytes(audit_bytes)),
        bytes.fromhex(generator_hash),
    )
    vector = vector_header + b"".join(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)

    manifest = {
        "type": "zkth06.player-bullet-spawn-vector",
        "schema_version": SCHEMA_VERSION,
        "format": "little-endian ZKPBV1",
        "header_bytes": HEADER.size,
        "record_bytes": RECORD_BYTES,
        "source_frames": len(frames),
        "spawn_calls": len(records),
        "initialized_bullets": total_allocations,
        "first_spawn_game_frame": first_frame,
        "last_spawn_game_frame": last_frame,
        "character": int(frames[0]["character"]),
        "shot_type": int(frames[0]["shot_type"]),
        "supported_power": {"minimum": 0, "maximum": 31, "ranks": [1, 2, 3]},
        "rank_call_counts": {str(key): value for key, value in rank_calls.items()},
        "maximum_pre_call_active_slots": max_active,
        "capacity_truncated_calls": 0,
        "dormant_carry_profile": "all four non-laser carried fields are zero before and after every call",
        "retail_anm_projection": "requested/active script, flags, position, and first script tick checked by generator",
        "target_executable_sha256": TARGET_SHA256,
        "replay_sha256": header.get("replay_sha256"),
        "retail_trace_sha256": sha256_bytes(retail_bytes),
        "reference_trace_sha256": comparison.get("reference_trace_sha256"),
        "comparison_artifact": args.comparison.name,
        "comparison_sha256": sha256_bytes(comparison_bytes),
        "static_audit_artifact": args.audit.name,
        "static_audit_sha256": sha256_bytes(audit_bytes),
        "static_audit_sealed_digest": audit["artifact_sha256"],
        "generator": {"path": "tools/build_player_bullets_vector.py", "sha256": generator_hash},
        "vector_sha256": sha256_bytes(vector),
        "claim_boundary": (
            "finite retail/reference evidence and a local per-call vector for Reimu-A ranks 1-3 "
            "SpawnBullets allocation and initialized geometry; pre-call slot states are independently "
            "observed and are not linked across calls through motion, ANM, or Enemy collision"
        ),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {len(records)} SpawnBullets calls / {total_allocations} bullets "
        f"({len(vector)} bytes, sha256={manifest['vector_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

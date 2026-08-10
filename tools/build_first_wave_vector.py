#!/usr/bin/env python3
"""Build the retail-bound complete Stage-1 first-wave state vector."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import arithmetic_obligations
import first_wave_audit


MAGIC = b"ZKFWV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8s8I32s32s32s32s32s32s")
FRAME = struct.Struct("<IHHI3IBBH")
ENEMY = struct.Struct("<BBHii7I")
BULLET = struct.Struct("<BBH3I3I2II3IiihBBhh3IiiIHHII")
HEADER_KIND = "zkth06.retail-anchor-header"
FRAME_KIND = "zkth06.retail-anchor-frame"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
REPLAY_SHA256 = "01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f"
COMPARISON_PROFILE = "enemy-collisions"
LAST_GAME_FRAME = 229
DEATH_FRAMES = (208, 213, 219, 224, 229)
COLLISION_SLOTS = (2, 3, 4, 0, 1)
SPAWN_FRAMES = (129, 145, 161, 177, 193)


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
    return [slot for slot, (left, right) in enumerate(zip(before, after, strict=True)) if left != right]


def expected_enemy_slots(frame: int) -> list[int]:
    return [
        slot
        for slot, (spawn, death) in enumerate(zip(SPAWN_FRAMES, DEATH_FRAMES, strict=True))
        if spawn <= frame < death
    ]


def validate_profile(frames: list[dict[str, Any]]) -> dict[str, Any]:
    if len(frames) < LAST_GAME_FRAME:
        raise ValueError("retail trace is shorter than the first-wave prefix")
    selected = frames[:LAST_GAME_FRAME]
    if [int(frame["game_frame"]) for frame in selected] != list(range(1, LAST_GAME_FRAME + 1)):
        raise ValueError("selected game frames are not contiguous")
    expected_hits = dict(zip(DEATH_FRAMES, COLLISION_SLOTS, strict=True))
    observed_hits: list[tuple[int, int]] = []
    prior_score = 0
    for frame in selected:
        game_frame = int(frame["game_frame"])
        if (
            int(frame["character"]) != 0
            or int(frame["shot_type"]) != 0
            or int(frame["current_power"]) != 0
            or int(frame["player_bomb_is_in_use"]) != 0
        ):
            raise ValueError(f"route left the Reimu-A rank-1 profile at frame {game_frame}")
        if bool(frame.get("player_damage_trace_overflow")):
            raise ValueError(f"damage trace overflow at frame {game_frame}")
        enemies = frame.get("enemies", [])
        if [int(enemy["slot"]) for enemy in enemies] != expected_enemy_slots(game_frame):
            raise ValueError(f"unexpected Enemy slots at frame {game_frame}")
        active = frame["player_bullets_frame"]["active_slots"]
        active_states = {int(bullet["slot"]): int(bullet["state"]) for bullet in active}
        expected_collided = {
            slot for death, slot in expected_hits.items() if death <= game_frame
        }
        if {slot for slot, state in active_states.items() if state == 2} != expected_collided:
            raise ValueError(f"unexpected collided pool at frame {game_frame}")
        if any(state not in (1, 2) for state in active_states.values()):
            raise ValueError(f"invalid active bullet state at frame {game_frame}")
        hits = [call for call in frame.get("player_damage_calls", []) if int(call["damage"]) != 0]
        if game_frame in expected_hits:
            if len(hits) != 1 or int(hits[0]["damage"]) != 48:
                raise ValueError(f"expected one 48-damage hit at frame {game_frame}")
            slot = expected_hits[game_frame]
            if changed_slots(hits[0]) != [slot]:
                raise ValueError(f"unexpected collision slot at frame {game_frame}")
            observed_hits.append((game_frame, slot))
            expected_score = prior_score + 390
        else:
            if hits:
                raise ValueError(f"unexpected damaging call at frame {game_frame}")
            expected_score = prior_score
        score = int(frame["score"])
        if score != expected_score:
            raise ValueError(f"unexpected score writer at frame {game_frame}: {score} != {expected_score}")
        prior_score = score
    final = selected[-1]
    if int(final["score"]) != 1950 or final["enemies"]:
        raise ValueError("frame-229 state does not close the first wave")
    return {
        "damage_calls": sum(len(frame.get("player_damage_calls", [])) for frame in selected),
        "damaging_calls": len(observed_hits),
        "collisions": observed_hits,
        "final_collided_bullets": sum(
            int(bullet["state"]) == 2
            for bullet in final["player_bullets_frame"]["active_slots"]
        ),
        "final_rng_generation": int(final["rng_generation"]),
        "final_score": int(final["score"]),
    }


def pack_enemy(enemy: dict[str, Any]) -> bytes:
    position = raw_vec(enemy["position_bits"], 3)
    axis = raw_vec(enemy["axis_speed_bits"], 3)
    return ENEMY.pack(
        int(enemy["slot"]),
        int(bool(int(enemy["flags"][1]) & 4)),
        0,
        int(enemy["ecl_time"]),
        int(enemy["life"]),
        *position,
        axis[0],
        axis[1],
        raw_u32(enemy["angle_bits"]),
        raw_u32(enemy["angular_velocity_bits"]),
    )


def pack_bullet(bullet: dict[str, Any]) -> bytes:
    return BULLET.pack(
        int(bullet["slot"]),
        int(bullet["state"]),
        0,
        *raw_vec(bullet["position_bits"], 3),
        *raw_vec(bullet["size_bits"], 3),
        *raw_vec(bullet["velocity_bits"], 2),
        raw_u32(bullet["sideways_motion_bits"]),
        *raw_vec(bullet["unk_134_bits"], 3),
        int(bullet["timer_previous"]),
        int(bullet["timer_current"]),
        int(bullet["damage"]),
        int(bullet["type"]),
        0,
        int(bullet["unk_152"]),
        int(bullet["spawn_position_idx"]),
        *raw_vec(bullet["sprite_position_bits"], 3),
        int(bullet["sprite_timer_previous"]),
        int(bullet["sprite_timer_current"]),
        int(bullet["sprite_flags"]),
        int(bullet["sprite_active_index"]),
        int(bullet["sprite_anm_file_index"]),
        *raw_vec(bullet["sprite_size_bits"], 2),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("reference_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--parent-vector", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    header, frames, retail_bytes = load_trace(args.retail_trace)
    reference_bytes = args.reference_trace.read_bytes()
    comparison, comparison_bytes = load_json(args.comparison)
    audit, audit_bytes = load_json(args.audit)
    parent_bytes = args.parent_vector.read_bytes()
    if header.get("target_executable_sha256") != TARGET_SHA256:
        raise ValueError("retail trace is bound to another executable")
    if header.get("replay_sha256") != REPLAY_SHA256:
        raise ValueError("retail trace is bound to another replay")
    if (
        comparison.get("status") != "match"
        or comparison.get("comparison_profile") != COMPARISON_PROFILE
        or int(comparison.get("compared_frames", 0)) < LAST_GAME_FRAME
        or comparison.get("retail_trace_sha256") != sha256_bytes(retail_bytes)
        or comparison.get("reference_trace_sha256") != sha256_bytes(reference_bytes)
    ):
        raise ValueError("comparison is stale or does not cover the selected trace")
    if (
        audit.get("kind") != first_wave_audit.KIND
        or arithmetic_obligations.document_digest(audit) != audit.get("artifact_sha256")
        or audit.get("inputs", {}).get("executable_sha256") != TARGET_SHA256
    ):
        raise ValueError("first-wave audit is invalid")

    metrics = validate_profile(frames)
    records = bytearray()
    for frame in frames[:LAST_GAME_FRAME]:
        enemies = frame["enemies"]
        bullets = frame["player_bullets_frame"]["active_slots"]
        collision_count = sum(int(bullet["state"]) == 2 for bullet in bullets)
        records.extend(
            FRAME.pack(
                int(frame["game_frame"]),
                int(frame["input"]),
                len(bullets),
                int(frame["score"]),
                *raw_vec(frame["player_last_enemy_hit_bits"], 3),
                len(enemies),
                collision_count,
                0,
            )
        )
        for enemy in enemies:
            records.extend(pack_enemy(enemy))
        for bullet in bullets:
            records.extend(pack_bullet(bullet))

    hashes = [
        bytes.fromhex(sha256_bytes(retail_bytes)),
        bytes.fromhex(sha256_bytes(reference_bytes)),
        bytes.fromhex(sha256_bytes(comparison_bytes)),
        bytes.fromhex(sha256_bytes(audit_bytes)),
        bytes.fromhex(sha256_bytes(parent_bytes)),
        bytes.fromhex(arithmetic_obligations.sha256_file(Path(__file__).resolve())),
    ]
    vector = HEADER.pack(
        MAGIC,
        SCHEMA_VERSION,
        HEADER.size,
        FRAME.size,
        ENEMY.size,
        BULLET.size,
        len(frames),
        LAST_GAME_FRAME,
        LAST_GAME_FRAME - 1,
        *hashes,
    ) + records
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    document = {
        "type": "zkth06.first-wave-vector",
        "schema_version": SCHEMA_VERSION,
        "vector_sha256": sha256_bytes(vector),
        "vector_bytes": len(vector),
        "source_frames": len(frames),
        "selected_frames": LAST_GAME_FRAME,
        "tested_transitions": LAST_GAME_FRAME - 1,
        "anchor_game_frame": 1,
        "incremental_anchor_game_frame": 208,
        "final_game_frame": LAST_GAME_FRAME,
        "record_sizes": {
            "header": HEADER.size,
            "frame": FRAME.size,
            "enemy": ENEMY.size,
            "bullet": BULLET.size,
        },
        "bindings": {
            "retail_trace_sha256": hashes[0].hex(),
            "reference_trace_sha256": hashes[1].hex(),
            "comparison_sha256": hashes[2].hex(),
            "static_audit_sha256": hashes[3].hex(),
            "parent_early_gameplay_vector_sha256": hashes[4].hex(),
            "generator_sha256": hashes[5].hex(),
            "target_executable_sha256": TARGET_SHA256,
            "replay_sha256": REPLAY_SHA256,
        },
        "metrics": metrics,
        "claim_boundary": (
            "finite complete retained-state vector from frame 1 through the fifth first-wave death "
            "at frame 229; omitted death-item state first feeds score/power at frame 249"
        ),
    }
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if "/home/" in text:
        raise AssertionError("manifest contains a local path")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(text, encoding="utf-8")
    print(json.dumps({"status": "built", "bytes": len(vector), "sha256": sha256_bytes(vector), **metrics}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

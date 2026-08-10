#!/usr/bin/env python3
"""Build the retail-bound first Item-feedback state vector."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import arithmetic_obligations
import first_item_audit


MAGIC = b"ZKFIV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8s9I32s32s32s32s32s32s")
FRAME = struct.Struct("<IHHI3I4BHiHBBH")
ENEMY = struct.Struct("<BBHii7I")
BULLET = struct.Struct("<BBH3I3I2II3IiihBBhh3IiiIHHII")
ITEM = struct.Struct("<BBH9Iii4B")
HEADER_KIND = "zkth06.retail-anchor-header"
FRAME_KIND = "zkth06.retail-anchor-frame"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
REPLAY_SHA256 = "01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f"
COMPARISON_PROFILE = "items"
LAST_GAME_FRAME = 249
DEATH_FRAMES = (208, 213, 219, 224, 229)
COLLISION_SLOTS = (2, 3, 4, 0, 1)
COLLISION_RECLAIM_FRAMES = (238, 243, 249)


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


def expected_random_spawn_index(frame: int) -> int:
    return 1 + sum(death <= frame for death in DEATH_FRAMES)


def validate_profile(frames: list[dict[str, Any]]) -> dict[str, Any]:
    if len(frames) < LAST_GAME_FRAME:
        raise ValueError("retail trace is shorter than the first-Item prefix")
    selected = frames[:LAST_GAME_FRAME]
    if [int(frame["game_frame"]) for frame in selected] != list(range(1, LAST_GAME_FRAME + 1)):
        raise ValueError("selected game frames are not contiguous")
    expected_hits = dict(zip(DEATH_FRAMES, COLLISION_SLOTS, strict=True))
    prior_collided: set[int] = set()
    reclaimed: list[int] = []
    for frame in selected:
        game_frame = int(frame["game_frame"])
        items = frame.get("items_frame")
        if not isinstance(items, dict):
            raise ValueError(f"missing Item projection at frame {game_frame}")
        if int(items["random_spawn_index"]) != expected_random_spawn_index(game_frame):
            raise ValueError(f"unexpected random-drop cursor at frame {game_frame}")
        spawned = game_frame >= 219
        active_expected = 219 <= game_frame < 249
        if int(items["next_index"]) != int(spawned):
            raise ValueError(f"unexpected Item allocator cursor at frame {game_frame}")
        if int(items["random_table_index"]) != int(spawned):
            raise ValueError(f"unexpected random table cursor at frame {game_frame}")
        if int(items["item_count"]) != int(spawned):
            raise ValueError(f"unexpected Item count at frame {game_frame}")
        active_items = items["active_slots"]
        if len(active_items) != int(active_expected):
            raise ValueError(f"unexpected active Item count at frame {game_frame}")
        if active_items:
            item = active_items[0]
            if (
                int(item["slot"]) != 0
                or int(item["item_type"]) != 0
                or int(item["state"]) != 0
                or int(item["is_in_use"]) != 1
                or int(item["unk_142"]) != 1
                or raw_vec(item["target_position_bits"], 3) != (0, 0, 0)
                or int(item["timer_current"]) != game_frame - 218
                or int(item["timer_previous"]) != game_frame - 219
            ):
                raise ValueError(f"unexpected Item state at frame {game_frame}")
        power_expected = int(game_frame >= 249)
        score_expected = 1960 if game_frame >= 249 else 1950 if game_frame >= 229 else None
        if int(frame["current_power"]) != power_expected or int(frame["subrank"]) != power_expected:
            raise ValueError(f"unexpected Item feedback state at frame {game_frame}")
        if score_expected is not None and int(frame["score"]) != score_expected:
            raise ValueError(f"unexpected post-wave score at frame {game_frame}")

        bullets = frame["player_bullets_frame"]["active_slots"]
        collided = {int(bullet["slot"]) for bullet in bullets if int(bullet["state"]) == 2}
        removed = prior_collided - collided
        if removed:
            if len(removed) != 1:
                raise ValueError(f"multiple collision ANM exits at frame {game_frame}")
            reclaimed.append(game_frame)
        prior_collided = collided
        hits = [call for call in frame.get("player_damage_calls", []) if int(call["damage"]) != 0]
        if game_frame in expected_hits:
            if len(hits) != 1 or int(hits[0]["damage"]) != 48:
                raise ValueError(f"expected one Enemy hit at frame {game_frame}")
            if changed_slots(hits[0]) != [expected_hits[game_frame]]:
                raise ValueError(f"unexpected collision slot at frame {game_frame}")
        elif hits:
            raise ValueError(f"unexpected Enemy hit at frame {game_frame}")
    if tuple(reclaimed) != COLLISION_RECLAIM_FRAMES:
        raise ValueError(f"unexpected collision-ANM reclamation frames: {reclaimed}")
    final = selected[-1]
    return {
        "item_spawn_game_frame": 219,
        "item_collection_game_frame": 249,
        "final_score": int(final["score"]),
        "final_power": int(final["current_power"]),
        "final_subrank": int(final["subrank"]),
        "final_random_spawn_index": int(final["items_frame"]["random_spawn_index"]),
        "final_random_table_index": int(final["items_frame"]["random_table_index"]),
        "collision_anm_reclamation_frames": reclaimed,
        "final_active_bullets": len(final["player_bullets_frame"]["active_slots"]),
        "final_collided_bullets": sum(
            int(bullet["state"]) == 2 for bullet in final["player_bullets_frame"]["active_slots"]
        ),
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


def pack_item(item: dict[str, Any]) -> bytes:
    return ITEM.pack(
        int(item["slot"]),
        int(item["item_type"]),
        0,
        *raw_vec(item["current_position_bits"], 3),
        *raw_vec(item["start_position_bits"], 3),
        *raw_vec(item["target_position_bits"], 3),
        int(item["timer_previous"]),
        int(item["timer_current"]),
        int(item["state"]),
        int(item["unk_142"]),
        int(item["is_in_use"]),
        0,
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
        audit.get("kind") != first_item_audit.KIND
        or arithmetic_obligations.document_digest(audit) != audit.get("artifact_sha256")
        or audit.get("inputs", {}).get("executable_sha256") != TARGET_SHA256
    ):
        raise ValueError("first-Item audit is invalid")

    metrics = validate_profile(frames)
    records = bytearray()
    for frame in frames[:LAST_GAME_FRAME]:
        enemies = frame["enemies"]
        bullets = frame["player_bullets_frame"]["active_slots"]
        items = frame["items_frame"]
        active_items = items["active_slots"]
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
                len(active_items),
                int(items["random_spawn_index"]),
                int(frame["current_power"]),
                int(frame["subrank"]),
                int(items["next_index"]),
                int(items["random_table_index"]),
                int(items["item_count"]),
                0,
            )
        )
        for enemy in enemies:
            records.extend(pack_enemy(enemy))
        for bullet in bullets:
            records.extend(pack_bullet(bullet))
        for item in active_items:
            records.extend(pack_item(item))

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
        ITEM.size,
        len(frames),
        LAST_GAME_FRAME,
        LAST_GAME_FRAME - 1,
        *hashes,
    ) + records
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    document = {
        "type": "zkth06.first-item-vector",
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
            "item": ITEM.size,
        },
        "bindings": {
            "retail_trace_sha256": hashes[0].hex(),
            "reference_trace_sha256": hashes[1].hex(),
            "comparison_sha256": hashes[2].hex(),
            "static_audit_sha256": hashes[3].hex(),
            "parent_first_wave_vector_sha256": hashes[4].hex(),
            "generator_sha256": hashes[5].hex(),
            "target_executable_sha256": TARGET_SHA256,
            "replay_sha256": REPLAY_SHA256,
        },
        "metrics": metrics,
        "claim_boundary": (
            "finite complete retained-state vector through the first death-Item spawn, motion, "
            "collection, and score/power/subrank feedback at frame 249"
        ),
    }
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if "/home/" in text:
        raise AssertionError("manifest contains a local path")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {"status": "built", "bytes": len(vector), "sha256": sha256_bytes(vector), **metrics},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

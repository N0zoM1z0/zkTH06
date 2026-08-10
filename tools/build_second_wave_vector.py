#!/usr/bin/env python3
"""Build the retail-bound Stage-1 second-wave state vector."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import arithmetic_obligations
import second_wave_audit


MAGIC = b"ZKSWV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8s10I32s32s32s32s32s32s")
FRAME = struct.Struct("<II3IHI2B2HiH4B2HiiH")
ENEMY = struct.Struct("<BBHii7I")
BULLET = struct.Struct("<BBH3I3I2II3IiihBBhh3IiiIHHII")
ITEM = struct.Struct("<BBH9Iii4B")
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
REPLAY_SHA256 = "01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f"
FIRST_RECORD = 250
LAST_FRAME = 350
EXPECTED_DEATHS = [328, 331, 335, 343, 350]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def vec(value: Any, count: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"expected {count}-element vector")
    return tuple(raw(item) for item in value)


def load_trace(path: Path, retail: bool) -> tuple[dict[str, Any] | None, list[dict[str, Any]], bytes]:
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    header = rows.pop(0) if retail else None
    return header, rows, data


def pack_enemy(enemy: dict[str, Any]) -> bytes:
    return ENEMY.pack(
        int(enemy["slot"]),
        int(bool(int(enemy["flags"][1]) & 4)),
        0,
        int(enemy["ecl_time"]),
        int(enemy["life"]),
        *vec(enemy["position_bits"], 3),
        *vec(enemy["axis_speed_bits"], 3)[:2],
        raw(enemy["angle_bits"]),
        raw(enemy["angular_velocity_bits"]),
    )


def pack_bullet(bullet: dict[str, Any]) -> bytes:
    return BULLET.pack(
        int(bullet["slot"]), int(bullet["state"]), 0,
        *vec(bullet["position_bits"], 3), *vec(bullet["size_bits"], 3),
        *vec(bullet["velocity_bits"], 2), raw(bullet["sideways_motion_bits"]),
        *vec(bullet["unk_134_bits"], 3), int(bullet["timer_previous"]),
        int(bullet["timer_current"]), int(bullet["damage"]), int(bullet["type"]), 0,
        int(bullet["unk_152"]), int(bullet["spawn_position_idx"]),
        *vec(bullet["sprite_position_bits"], 3), int(bullet["sprite_timer_previous"]),
        int(bullet["sprite_timer_current"]), int(bullet["sprite_flags"]),
        int(bullet["sprite_active_index"]), int(bullet["sprite_anm_file_index"]),
        *vec(bullet["sprite_size_bits"], 2),
    )


def pack_item(item: dict[str, Any]) -> bytes:
    return ITEM.pack(
        int(item["slot"]), int(item["item_type"]), 0,
        *vec(item["current_position_bits"], 3), *vec(item["start_position_bits"], 3),
        *vec(item["target_position_bits"], 3), int(item["timer_previous"]),
        int(item["timer_current"]), int(item["state"]), int(item["unk_142"]),
        int(item["is_in_use"]), 0,
    )


def validate(frames: list[dict[str, Any]]) -> dict[str, Any]:
    if len(frames) < LAST_FRAME or [int(row["game_frame"]) for row in frames[:LAST_FRAME]] != list(range(1, LAST_FRAME + 1)):
        raise ValueError("retail trace does not contain a contiguous 350-frame prefix")
    deaths: list[int] = []
    prior_slots: set[int] = set()
    spawn_frames: list[int] = []
    for frame in frames[:LAST_FRAME]:
        game_frame = int(frame["game_frame"])
        enemy_slots = {int(enemy["slot"]) for enemy in frame["enemies"]}
        if len(enemy_slots - prior_slots) > 0:
            spawn_frames.extend([game_frame] * len(enemy_slots - prior_slots))
        if game_frame >= FIRST_RECORD and len(prior_slots - enemy_slots) > 0:
            deaths.extend([game_frame] * len(prior_slots - enemy_slots))
        prior_slots = enemy_slots
        enemy_bullets = frame["enemy_bullets_frame"]
        if (
            enemy_bullets["active_slots"]
            or int(enemy_bullets["next_index"]) != 0
            or int(enemy_bullets["bullet_count"]) != 0
            or int(enemy_bullets["timer_current"]) != game_frame
            or int(enemy_bullets["timer_previous"]) != game_frame - 1
        ):
            raise ValueError(f"unexpected Enemy-bullet state at frame {game_frame}")
    # Slot 0 is reused at 337, so set differences do not expose that spawn;
    # the full expected active-state schedule is asserted below.
    expected_active = {
        257: [0], 273: [0, 1], 289: [0, 1, 2], 305: [0, 1, 2, 3],
        321: [0, 1, 2, 3, 4], 328: [1, 2, 3, 4], 331: [1, 2, 3],
        335: [2, 3], 337: [0, 2, 3], 343: [0, 3], 350: [0],
    }
    for game_frame, slots in expected_active.items():
        actual = [int(enemy["slot"]) for enemy in frames[game_frame - 1]["enemies"]]
        if actual != slots:
            raise ValueError(f"unexpected Enemy slots at frame {game_frame}: {actual}")
    if deaths != EXPECTED_DEATHS:
        raise ValueError(f"unexpected second-wave death frames: {deaths}")
    final = frames[LAST_FRAME - 1]
    if (int(final["rng_seed"]), int(final["rng_generation"])) != (37443, 342):
        raise ValueError("unexpected final RNG")
    return {
        "timeline_spawns": [257, 273, 289, 305, 321, 337],
        "enemy_deaths": deaths,
        "final_score": int(final["score"]),
        "final_rng_seed": int(final["rng_seed"]),
        "final_rng_generation": int(final["rng_generation"]),
        "final_active_enemies": len(final["enemies"]),
        "final_active_items": len(final["items_frame"]["active_slots"]),
        "enemy_bullet_active_frames": 0,
    }


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

    header, frames, retail_data = load_trace(args.retail_trace, True)
    _, reference_frames, reference_data = load_trace(args.reference_trace, False)
    comparison_data = args.comparison.read_bytes()
    comparison = json.loads(comparison_data)
    audit_data = args.audit.read_bytes()
    audit = json.loads(audit_data)
    parent_data = args.parent_vector.read_bytes()
    if header is None or header.get("target_executable_sha256") != TARGET_SHA256 or header.get("replay_sha256") != REPLAY_SHA256:
        raise ValueError("retail trace binding mismatch")
    if len(frames) != len(reference_frames):
        raise ValueError("trace length mismatch")
    if (
        comparison.get("status") != "match"
        or comparison.get("comparison_profile") != "enemy-bullets"
        or int(comparison.get("compared_frames", 0)) < LAST_FRAME
        or comparison.get("retail_trace_sha256") != sha256(retail_data)
        or comparison.get("reference_trace_sha256") != sha256(reference_data)
    ):
        raise ValueError("stale comparison")
    if audit.get("kind") != second_wave_audit.KIND or arithmetic_obligations.document_digest(audit) != audit.get("artifact_sha256"):
        raise ValueError("invalid second-wave audit")
    metrics = validate(frames)

    inputs = b"".join(struct.pack("<H", int(frame["input"])) for frame in frames[:LAST_FRAME])
    records = bytearray()
    for frame in frames[FIRST_RECORD - 1 : LAST_FRAME]:
        enemies = frame["enemies"]
        items = frame["items_frame"]
        active_items = items["active_slots"]
        bullets = frame["player_bullets_frame"]["active_slots"]
        collided = sum(int(bullet["state"]) == 2 for bullet in bullets)
        enemy_bullets = frame["enemy_bullets_frame"]
        records.extend(FRAME.pack(
            int(frame["game_frame"]), int(frame["score"]), *vec(frame["player_last_enemy_hit_bits"], 3),
            int(frame["rng_seed"]), int(frame["rng_generation"]),
            int(items["random_spawn_index"]), int(items["random_table_index"]),
            int(items["next_index"]), int(items["item_count"]), int(frame["subrank"]),
            int(frame["current_power"]), len(enemies), len(active_items), len(bullets), collided,
            int(enemy_bullets["next_index"]), int(enemy_bullets["bullet_count"]),
            int(enemy_bullets["timer_previous"]), int(enemy_bullets["timer_current"]),
            len(enemy_bullets["active_slots"]),
        ))
        for enemy in enemies: records.extend(pack_enemy(enemy))
        for bullet in bullets: records.extend(pack_bullet(bullet))
        for item in active_items: records.extend(pack_item(item))

    builder_data = Path(__file__).read_bytes()
    hashes = [retail_data, reference_data, comparison_data, audit_data, parent_data, builder_data]
    vector = HEADER.pack(
        MAGIC, SCHEMA_VERSION, HEADER.size, FRAME.size, ENEMY.size, BULLET.size, ITEM.size,
        LAST_FRAME, FIRST_RECORD, LAST_FRAME - FIRST_RECORD + 1, LAST_FRAME,
        *(bytes.fromhex(sha256(value)) for value in hashes),
    ) + inputs + records
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    document = {
        "type": "zkth06.second-wave-vector",
        "schema_version": SCHEMA_VERSION,
        "vector_sha256": sha256(vector),
        "vector_bytes": len(vector),
        "source_frames": len(frames),
        "input_frames": LAST_FRAME,
        "first_record_game_frame": FIRST_RECORD,
        "last_game_frame": LAST_FRAME,
        "incremental_transitions": LAST_FRAME - 249,
        "bindings": {
            "target_executable_sha256": TARGET_SHA256,
            "replay_sha256": REPLAY_SHA256,
            "retail_trace_sha256": sha256(retail_data),
            "reference_trace_sha256": sha256(reference_data),
            "comparison_sha256": sha256(comparison_data),
            "audit_sha256": sha256(audit_data),
            "parent_vector_sha256": sha256(parent_data),
            "builder_sha256": sha256(builder_data),
        },
        "metrics": metrics,
        "claim_boundary": (
            "frame-by-frame derived canonical projection through second-group death; Enemy-bullet pool "
            "is explicitly empty, not an omitted subsystem"
        ),
    }
    args.manifest.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"vector": str(args.output), "sha256": sha256(vector), "bytes": len(vector), **metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Convert the second-wave vector to replay-only OpenVM input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKSWV1\0\0"
INPUT_MAGIC = b"ZKSWI1\0\0"
SCHEMA_VERSION = 1
PROFILE_FLAGS = 15
VECTOR_HEADER = struct.Struct("<8s10I32s32s32s32s32s32s")
VECTOR_FRAME = struct.Struct("<II3IHI2B2HiH4B2HiiH")
VECTOR_ENEMY = struct.Struct("<BBHii7I")
VECTOR_BULLET = struct.Struct("<BBH3I3I2II3IiihBBhh3IiiIHHII")
VECTOR_ITEM = struct.Struct("<BBH9Iii4B")
INPUT_HEADER = struct.Struct("<8sIII4B")
SUMMARY = struct.Struct("<4IHI2B2HiH4B2HiH2I32s")
STATE_DOMAIN = b"zkTH06/second-wave/projection/v1\0"
STATEMENT_DOMAIN = b"zkTH06/openvm/second-wave/v1\0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vector", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    vector = args.vector.read_bytes()
    values = VECTOR_HEADER.unpack_from(vector)
    (
        magic, schema, header_bytes, frame_bytes, enemy_bytes, bullet_bytes, item_bytes,
        input_frames, first_record, record_count, last_frame,
        retail_hash, reference_hash, comparison_hash, audit_hash, parent_hash, generator_hash,
    ) = values
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported second-wave vector")
    if (header_bytes, frame_bytes, enemy_bytes, bullet_bytes, item_bytes) != (
        VECTOR_HEADER.size, VECTOR_FRAME.size, VECTOR_ENEMY.size, VECTOR_BULLET.size, VECTOR_ITEM.size
    ):
        raise ValueError("unexpected vector layout")
    if (input_frames, first_record, record_count, last_frame) != (350, 250, 101, 350):
        raise ValueError("unexpected vector profile")
    input_offset = header_bytes
    input_bytes = vector[input_offset : input_offset + input_frames * 2]
    if len(input_bytes) != input_frames * 2:
        raise ValueError("truncated replay inputs")
    payload = INPUT_HEADER.pack(INPUT_MAGIC, SCHEMA_VERSION, input_frames, record_count, 0, 0, PROFILE_FLAGS, 0) + input_bytes

    offset = input_offset + len(input_bytes)
    projection = hashlib.sha256(STATE_DOMAIN)
    maximum_enemies = 0
    maximum_items = 0
    final: tuple[int, ...] | None = None
    for index in range(record_count):
        start = offset
        frame = VECTOR_FRAME.unpack_from(vector, offset)
        offset += frame_bytes
        if frame[0] != first_record + index:
            raise ValueError(f"non-contiguous state record {index}")
        enemy_count, item_count, bullet_count = frame[13], frame[14], frame[15]
        maximum_enemies = max(maximum_enemies, enemy_count)
        maximum_items = max(maximum_items, item_count)
        prior = -1
        for _ in range(enemy_count):
            enemy = VECTOR_ENEMY.unpack_from(vector, offset)
            if enemy[0] <= prior or enemy[2] != 0:
                raise ValueError("invalid Enemy slot ordering")
            prior = enemy[0]
            offset += enemy_bytes
        prior = -1
        collided = 0
        for _ in range(bullet_count):
            bullet = VECTOR_BULLET.unpack_from(vector, offset)
            if bullet[0] <= prior or bullet[1] not in (1, 2) or bullet[2] != 0:
                raise ValueError("invalid Player-bullet record")
            prior = bullet[0]
            collided += int(bullet[1] == 2)
            offset += bullet_bytes
        prior = -1
        for _ in range(item_count):
            item = VECTOR_ITEM.unpack_from(vector, offset)
            if item[0] <= prior or item[2] != 0 or item[-1] != 0:
                raise ValueError("invalid Item slot ordering")
            prior = item[0]
            offset += item_bytes
        if collided != frame[16] or frame[21] != 0:
            raise ValueError("state count mismatch")
        projection.update(vector[start:offset])
        final = frame
    if offset != len(vector) or final is None:
        raise ValueError("trailing or missing vector bytes")

    projection_digest = projection.digest()
    summary = SUMMARY.pack(
        final[0], input_frames, record_count, final[1], final[5], final[6], final[7], final[8],
        final[9], final[10], final[11], final[12], final[13], final[14], final[15], final[16],
        final[17], final[18], final[20], final[21], maximum_enemies, maximum_items, projection_digest,
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"input": ["0x01" + payload.hex()]}, separators=(",", ":")) + "\n", encoding="utf-8")
    report = {
        "type": "zkth06.openvm-second-wave-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "input_frames": input_frames,
        "incremental_transitions": record_count,
        "expected_final_game_frame": final[0],
        "expected_score": final[1],
        "expected_rng_seed": final[5],
        "expected_rng_generation": final[6],
        "expected_random_spawn_index": final[7],
        "expected_random_table_index": final[8],
        "expected_item_next_index": final[9],
        "expected_item_count": final[10],
        "expected_subrank": final[11],
        "expected_power": final[12],
        "expected_remaining_enemies": final[13],
        "expected_active_items": final[14],
        "expected_active_player_bullets": final[15],
        "expected_collided_player_bullets": final[16],
        "expected_enemy_bullet_next_index": final[17],
        "expected_enemy_bullet_count": final[18],
        "expected_enemy_bullet_timer": final[20],
        "expected_active_enemy_bullets": final[21],
        "expected_maximum_enemies": maximum_enemies,
        "expected_maximum_items": maximum_items,
        "expected_projection_sha256": projection_digest.hex(),
        "expected_statement_sha256": statement.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement)),
        "bindings": {
            "retail_trace_sha256": retail_hash.hex(), "reference_trace_sha256": reference_hash.hex(),
            "comparison_sha256": comparison_hash.hex(), "audit_sha256": audit_hash.hex(),
            "parent_vector_sha256": parent_hash.hex(), "vector_generator_sha256": generator_hash.hex(),
        },
        "state_domain_ascii": STATE_DOMAIN.rstrip(b"\0").decode("ascii"),
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "claim_boundary": "private replay masks only; frame-249 state and all retained second-wave state are derived",
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "/home/" in rendered:
        raise AssertionError("report contains local absolute path")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": "built", "payload_bytes": len(payload), "statement_sha256": statement.hex()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

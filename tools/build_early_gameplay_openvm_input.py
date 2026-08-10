#!/usr/bin/env python3
"""Convert the linked early-gameplay vector to replay-only OpenVM input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKEGP1\0\0"
INPUT_MAGIC = b"ZKEGI1\0\0"
SCHEMA_VERSION = 1
PROFILE_FLAGS = 1
VECTOR_HEADER = struct.Struct("<8s7I32s32s32s32s32s32s")
VECTOR_FRAME = struct.Struct("<IHBBI3I")
VECTOR_ENEMY = struct.Struct("<BBHii7I")
INPUT_HEADER = struct.Struct("<8sII4BI")
STATE_PREFIX = struct.Struct("<II3IBB")
SUMMARY = struct.Struct("<8I32s")
STATE_DOMAIN = b"zkTH06/early-gameplay/projection/v1\0"
STATEMENT_DOMAIN = b"zkTH06/openvm/early-gameplay/v1\0"
NO_COLLISION = 0xFF


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vector", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--transitions", type=int)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vector = args.vector.read_bytes()
    if len(vector) < VECTOR_HEADER.size:
        raise ValueError("truncated early-gameplay vector")
    (
        magic,
        schema,
        header_bytes,
        frame_bytes,
        enemy_bytes,
        source_frames,
        selected_frames,
        tested_transitions,
        retail_trace_hash,
        reference_trace_hash,
        comparison_hash,
        audit_hash,
        ecl_hash,
        generator_hash,
    ) = VECTOR_HEADER.unpack_from(vector)
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported early-gameplay vector")
    if (
        header_bytes != VECTOR_HEADER.size
        or frame_bytes != VECTOR_FRAME.size
        or enemy_bytes != VECTOR_ENEMY.size
    ):
        raise ValueError("unexpected early-gameplay vector layout")
    if tested_transitions != selected_frames - 1:
        raise ValueError("non-contiguous early-gameplay profile")

    records: list[tuple[tuple[int, ...], list[bytes]]] = []
    offset = header_bytes
    for index in range(selected_frames):
        frame = VECTOR_FRAME.unpack_from(vector, offset)
        offset += frame_bytes
        if frame[0] != index + 1:
            raise ValueError(f"invalid early-gameplay frame {index}")
        enemies: list[bytes] = []
        prior_slot = -1
        for _ in range(frame[2]):
            raw = vector[offset : offset + enemy_bytes]
            if len(raw) != enemy_bytes:
                raise ValueError("truncated Enemy record")
            enemy = VECTOR_ENEMY.unpack(raw)
            if enemy[0] <= prior_slot or enemy[2] != 0 or enemy[1] not in (0, 1):
                raise ValueError(f"invalid Enemy record at frame {frame[0]}")
            prior_slot = enemy[0]
            enemies.append(raw)
            offset += enemy_bytes
        records.append((frame, enemies))
    if offset != len(vector):
        raise ValueError("early-gameplay vector has trailing or missing bytes")

    available = selected_frames - 1
    count = available if args.transitions is None else args.transitions
    if not 1 <= count <= available:
        raise ValueError(f"transitions must be in 1..{available}")
    chosen = records[: count + 1]
    first = chosen[0][0]
    if first != (1, 0, 0, NO_COLLISION, 0, 0xC479C000, 0xC479C000, 0):
        raise ValueError("vector does not begin at the fixed empty gameplay anchor")

    payload = bytearray(
        INPUT_HEADER.pack(
            INPUT_MAGIC,
            SCHEMA_VERSION,
            count,
            0,
            0,
            PROFILE_FLAGS,
            0,
            1,
        )
    )
    state_digest = hashlib.sha256(STATE_DOMAIN)
    damage_calls = 0
    collision_events = 0
    maximum_enemies = 0
    prior_collision = NO_COLLISION
    for index, (frame, enemies) in enumerate(chosen):
        game_frame, input_mask, enemy_count, collided, score, target_x, target_y, target_z = frame
        if enemy_count != len(enemies) or collided not in (NO_COLLISION, 2):
            raise ValueError(f"bad state prefix at frame {game_frame}")
        state_digest.update(
            STATE_PREFIX.pack(
                game_frame,
                score,
                target_x,
                target_y,
                target_z,
                collided,
                enemy_count,
            )
        )
        for raw in enemies:
            state_digest.update(raw)
        if index:
            payload.extend(struct.pack("<H", input_mask))
            collision_this_frame = int(prior_collision == NO_COLLISION and collided != NO_COLLISION)
            collision_events += collision_this_frame
            damage_calls += sum(VECTOR_ENEMY.unpack(raw)[1] for raw in enemies)
            damage_calls += collision_this_frame
        prior_collision = collided
        maximum_enemies = max(maximum_enemies, enemy_count)

    final = chosen[-1][0]
    projection_digest = state_digest.digest()
    collided_slot = 0xFFFF_FFFF if final[3] == NO_COLLISION else final[3]
    summary = SUMMARY.pack(
        final[0],
        count,
        final[4],
        damage_calls,
        collision_events,
        collided_slot,
        final[2],
        maximum_enemies,
        projection_digest,
    )
    statement_digest = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-early-gameplay-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "transitions": count,
        "character": 0,
        "shot_type": 0,
        "profile_flags": PROFILE_FLAGS,
        "source_frames": source_frames,
        "available_selected_frames": selected_frames,
        "expected_final_game_frame": final[0],
        "expected_score": final[4],
        "expected_damage_calls": damage_calls,
        "expected_collision_events": collision_events,
        "expected_collided_slot": collided_slot,
        "expected_remaining_enemies": final[2],
        "expected_maximum_enemies": maximum_enemies,
        "expected_projection_sha256": projection_digest.hex(),
        "retail_trace_sha256": retail_trace_hash.hex(),
        "reference_trace_sha256": reference_trace_hash.hex(),
        "comparison_sha256": comparison_hash.hex(),
        "static_audit_sha256": audit_hash.hex(),
        "stage1_ecl_sha256": ecl_hash.hex(),
        "vector_generator_sha256": generator_hash.hex(),
        "state_domain_ascii": STATE_DOMAIN.rstrip(b"\0").decode("ascii"),
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "private replay input masks only; the guest derives the enclosing Player/bullet and "
            "early-Enemy transitions from the fixed frame-1 anchor through the selected prefix"
        ),
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "/home/" in text:
        raise AssertionError("report contains a local absolute path")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "built",
                "transitions": count,
                "input_payload_bytes": len(payload),
                "expected_statement_sha256": statement_digest.hex(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Convert the complete first-wave vector to replay-only OpenVM input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKFWV1\0\0"
INPUT_MAGIC = b"ZKFWI1\0\0"
SCHEMA_VERSION = 1
PROFILE_FLAGS = 3
VECTOR_HEADER = struct.Struct("<8s8I32s32s32s32s32s32s")
VECTOR_FRAME = struct.Struct("<IHHI3IBBH")
VECTOR_ENEMY = struct.Struct("<BBHii7I")
VECTOR_BULLET = struct.Struct("<BBH3I3I2II3IiihBBhh3IiiIHHII")
INPUT_HEADER = struct.Struct("<8sII4BI")
STATE_PREFIX = struct.Struct("<II3IBBBB")
SUMMARY = struct.Struct("<9I32s")
STATE_DOMAIN = b"zkTH06/first-wave/projection/v1\0"
STATEMENT_DOMAIN = b"zkTH06/openvm/first-wave/v1\0"


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
        raise ValueError("truncated first-wave vector")
    (
        magic,
        schema,
        header_bytes,
        frame_bytes,
        enemy_bytes,
        bullet_bytes,
        source_frames,
        selected_frames,
        tested_transitions,
        retail_hash,
        reference_hash,
        comparison_hash,
        audit_hash,
        parent_vector_hash,
        generator_hash,
    ) = VECTOR_HEADER.unpack_from(vector)
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported first-wave vector")
    if (
        header_bytes != VECTOR_HEADER.size
        or frame_bytes != VECTOR_FRAME.size
        or enemy_bytes != VECTOR_ENEMY.size
        or bullet_bytes != VECTOR_BULLET.size
    ):
        raise ValueError("unexpected first-wave vector layout")
    if tested_transitions != selected_frames - 1:
        raise ValueError("non-contiguous first-wave profile")

    records: list[tuple[tuple[int, ...], list[bytes], list[bytes]]] = []
    offset = header_bytes
    for index in range(selected_frames):
        frame = VECTOR_FRAME.unpack_from(vector, offset)
        offset += frame_bytes
        if frame[0] != index + 1 or frame[9] != 0:
            raise ValueError(f"invalid first-wave frame {index}")
        enemies: list[bytes] = []
        prior_slot = -1
        for _ in range(frame[7]):
            raw = vector[offset : offset + enemy_bytes]
            enemy = VECTOR_ENEMY.unpack(raw)
            if len(raw) != enemy_bytes or enemy[0] <= prior_slot or enemy[2] != 0:
                raise ValueError(f"invalid Enemy record at frame {frame[0]}")
            prior_slot = enemy[0]
            enemies.append(raw)
            offset += enemy_bytes
        bullets: list[bytes] = []
        prior_slot = -1
        collisions = 0
        for _ in range(frame[2]):
            raw = vector[offset : offset + bullet_bytes]
            bullet = VECTOR_BULLET.unpack(raw)
            if (
                len(raw) != bullet_bytes
                or bullet[0] <= prior_slot
                or bullet[1] not in (1, 2)
                or bullet[2] != 0
            ):
                raise ValueError(f"invalid bullet record at frame {frame[0]}")
            prior_slot = bullet[0]
            collisions += int(bullet[1] == 2)
            bullets.append(raw)
            offset += bullet_bytes
        if len(enemies) != frame[7] or len(bullets) != frame[2] or collisions != frame[8]:
            raise ValueError(f"state count mismatch at frame {frame[0]}")
        records.append((frame, enemies, bullets))
    if offset != len(vector):
        raise ValueError("first-wave vector has trailing or missing bytes")

    available = selected_frames - 1
    count = available if args.transitions is None else args.transitions
    if not 1 <= count <= available:
        raise ValueError(f"transitions must be in 1..{available}")
    chosen = records[: count + 1]
    first = chosen[0][0]
    if first[0] != 1 or first[3] != 0 or first[7] != 0 or first[8] != 0:
        raise ValueError("vector does not begin at the empty frame-1 anchor")

    payload = bytearray(
        INPUT_HEADER.pack(INPUT_MAGIC, SCHEMA_VERSION, count, 0, 0, PROFILE_FLAGS, 0, 1)
    )
    state_digest = hashlib.sha256(STATE_DOMAIN)
    damage_calls = 0
    collision_events = 0
    maximum_enemies = 0
    prior_collisions = 0
    for index, (frame, enemies, bullets) in enumerate(chosen):
        game_frame, input_mask, active_count, score, target_x, target_y, target_z, enemy_count, collisions, reserved = frame
        state_digest.update(
            STATE_PREFIX.pack(
                game_frame,
                score,
                target_x,
                target_y,
                target_z,
                enemy_count,
                active_count,
                collisions,
                reserved,
            )
        )
        for raw in enemies:
            state_digest.update(raw)
        for raw in bullets:
            state_digest.update(raw)
        if index:
            payload.extend(struct.pack("<H", input_mask))
            new_collisions = collisions - prior_collisions
            if new_collisions not in (0, 1):
                raise ValueError(f"non-monotone collision prefix at frame {game_frame}")
            collision_events += new_collisions
            damage_calls += sum(VECTOR_ENEMY.unpack(raw)[1] for raw in enemies)
            damage_calls += new_collisions
        prior_collisions = collisions
        maximum_enemies = max(maximum_enemies, enemy_count)

    final, final_enemies, final_bullets = chosen[-1]
    projection_digest = state_digest.digest()
    summary = SUMMARY.pack(
        final[0],
        count,
        final[3],
        damage_calls,
        collision_events,
        final[8],
        len(final_bullets),
        len(final_enemies),
        maximum_enemies,
        projection_digest,
    )
    statement_digest = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-first-wave-input",
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
        "expected_score": final[3],
        "expected_damage_calls": damage_calls,
        "expected_collision_events": collision_events,
        "expected_collided_bullets": final[8],
        "expected_active_bullets": len(final_bullets),
        "expected_remaining_enemies": len(final_enemies),
        "expected_maximum_enemies": maximum_enemies,
        "expected_projection_sha256": projection_digest.hex(),
        "retail_trace_sha256": retail_hash.hex(),
        "reference_trace_sha256": reference_hash.hex(),
        "comparison_sha256": comparison_hash.hex(),
        "static_audit_sha256": audit_hash.hex(),
        "parent_early_gameplay_vector_sha256": parent_vector_hash.hex(),
        "vector_generator_sha256": generator_hash.hex(),
        "state_domain_ascii": STATE_DOMAIN.rstrip(b"\0").decode("ascii"),
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "private replay masks only; the guest derives the complete Player bullet pool and "
            "first-wave Enemy projection from the fixed frame-1 anchor"
        ),
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "/home/" in text:
        raise AssertionError("report contains a local absolute path")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text, encoding="utf-8")
    print(json.dumps({"status": "built", "transitions": count, "input_payload_bytes": len(payload), "expected_statement_sha256": statement_digest.hex()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

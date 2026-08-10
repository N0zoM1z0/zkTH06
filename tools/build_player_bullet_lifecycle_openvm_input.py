#!/usr/bin/env python3
"""Convert the linked Player/bullet lifecycle vector to OpenVM input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKPLV1\0\0"
INPUT_MAGIC = b"ZKPLI1\0\0"
SCHEMA_VERSION = 1
PROFILE_FLAGS = 1
VECTOR_HEADER = struct.Struct("<8s6I4B4I32s32s32s32s32s20x")
VECTOR_FRAME = struct.Struct("<IHBBiIIHBBiiIB3x")
VECTOR_BULLET = struct.Struct("<2Bh2h12IiIi3I2iI2H2I")
INPUT_HEADER = struct.Struct("<8sII4BI")
STATE_PREFIX = struct.Struct("<IBBiIIHiiIB")
SUMMARY = struct.Struct("<7I32s")
STATE_DOMAIN = b"zkTH06/player-bullet-lifecycle/state/v1\0"
STATEMENT_DOMAIN = b"zkTH06/openvm/player-bullet-lifecycle/v1\0"


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
        raise ValueError("truncated lifecycle vector")
    (
        magic,
        schema,
        header_bytes,
        frame_bytes,
        bullet_bytes,
        source_frames,
        selected_frames,
        character,
        shot_type,
        profile_flags,
        reserved,
        anchor_game_frame,
        last_game_frame,
        first_collision_frame,
        maximum_available_active,
        retail_trace_hash,
        reference_trace_hash,
        comparison_hash,
        audit_hash,
        generator_hash,
    ) = VECTOR_HEADER.unpack_from(vector)
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported lifecycle vector")
    if (
        header_bytes != VECTOR_HEADER.size
        or frame_bytes != VECTOR_FRAME.size
        or bullet_bytes != VECTOR_BULLET.size
    ):
        raise ValueError("unexpected lifecycle vector layout")
    if (character, shot_type, profile_flags, reserved) != (0, 0, PROFILE_FLAGS, 0):
        raise ValueError("unsupported lifecycle vector profile")
    if (anchor_game_frame, last_game_frame, first_collision_frame) != (1, 207, 208):
        raise ValueError("unexpected lifecycle frame boundary")

    records: list[tuple[tuple[int, ...], list[bytes]]] = []
    offset = header_bytes
    for index in range(selected_frames):
        frame = VECTOR_FRAME.unpack_from(vector, offset)
        offset += frame_bytes
        if frame[0] != index + anchor_game_frame or frame[9] != 0:
            raise ValueError(f"invalid lifecycle frame {index}")
        bullets: list[bytes] = []
        prior_slot = -1
        for _ in range(frame[13]):
            raw = vector[offset : offset + bullet_bytes]
            if len(raw) != bullet_bytes:
                raise ValueError("truncated active bullet record")
            bullet = VECTOR_BULLET.unpack(raw)
            if bullet[0] <= prior_slot or bullet[18] != 0:
                raise ValueError(f"invalid active bullet at frame {frame[0]}")
            prior_slot = bullet[0]
            bullets.append(raw)
            offset += bullet_bytes
        records.append((frame, bullets))
    if offset != len(vector):
        raise ValueError("lifecycle vector has trailing or missing bytes")

    available = selected_frames - 1
    count = available if args.transitions is None else args.transitions
    if not 1 <= count <= available:
        raise ValueError(f"transitions must be in 1..{available}")
    chosen = records[: count + 1]
    first = chosen[0][0]
    if first[:13] != (
        1,
        0,
        3,
        0,
        239,
        0x43400000,
        0x43C00000,
        0,
        0xFF,
        0,
        -999,
        -1,
        0,
    ) or first[13] != 0:
        raise ValueError("vector does not begin at the fixed empty lifecycle anchor")

    payload = bytearray(
        INPUT_HEADER.pack(
            INPUT_MAGIC,
            SCHEMA_VERSION,
            count,
            character,
            shot_type,
            profile_flags,
            reserved,
            anchor_game_frame,
        )
    )
    state_digest = hashlib.sha256(STATE_DOMAIN)
    initialized = 0
    reclaimed = 0
    maximum_active = 0
    previous_active = 0
    for index, (frame, bullets) in enumerate(chosen):
        (
            game_frame,
            input_mask,
            player_state,
            flags,
            invulnerability_timer,
            x_bits,
            y_bits,
            previous_input,
            _spawn_timer,
            _reserved,
            fire_previous,
            fire_current,
            spawn_call_count,
            active_count,
        ) = frame
        if active_count != len(bullets) or flags & ~0x07:
            raise ValueError(f"bad state prefix at frame {game_frame}")
        state_digest.update(
            STATE_PREFIX.pack(
                game_frame,
                player_state,
                flags & 0x07,
                invulnerability_timer,
                x_bits,
                y_bits,
                previous_input,
                fire_previous,
                fire_current,
                spawn_call_count,
                active_count,
            )
        )
        for raw in bullets:
            state_digest.update(raw)
        if index:
            payload.extend(struct.pack("<H", input_mask))
            new_bullets = sum(VECTOR_BULLET.unpack(raw)[19] == 0 for raw in bullets)
            initialized += new_bullets
            reclaimed_this_frame = previous_active + new_bullets - active_count
            if reclaimed_this_frame < 0:
                raise ValueError(f"impossible active-slot recurrence at frame {game_frame}")
            reclaimed += reclaimed_this_frame
        previous_active = active_count
        maximum_active = max(maximum_active, active_count)

    final = chosen[-1][0]
    lifecycle_digest = state_digest.digest()
    summary = SUMMARY.pack(
        final[0],
        count,
        final[12],
        initialized,
        reclaimed,
        final[13],
        maximum_active,
        lifecycle_digest,
    )
    statement_digest = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-player-bullet-lifecycle-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "transitions": count,
        "character": character,
        "shot_type": shot_type,
        "profile_flags": profile_flags,
        "source_frames": source_frames,
        "available_selected_frames": selected_frames,
        "available_last_game_frame": last_game_frame,
        "first_external_collision_game_frame": first_collision_frame,
        "maximum_available_active_slots": maximum_available_active,
        "expected_final_game_frame": final[0],
        "expected_spawn_calls": final[12],
        "expected_initialized_bullets": initialized,
        "expected_update_reclamations": reclaimed,
        "expected_final_active_slots": final[13],
        "expected_maximum_active_slots": maximum_active,
        "expected_lifecycle_sha256": lifecycle_digest.hex(),
        "retail_trace_sha256": retail_trace_hash.hex(),
        "reference_trace_sha256": reference_trace_hash.hex(),
        "comparison_sha256": comparison_hash.hex(),
        "static_audit_sha256": audit_hash.hex(),
        "vector_generator_sha256": generator_hash.hex(),
        "state_domain_ascii": STATE_DOMAIN.rstrip(b"\0").decode("ascii"),
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "private replay input masks only; the guest derives and commits every Player/bullet "
            "state from the fixed empty frame-1 anchor through the selected collision-free prefix"
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

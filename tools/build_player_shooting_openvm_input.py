#!/usr/bin/env python3
"""Convert a closed Player shooting vector into an OpenVM private input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKSHV1\0\0"
INPUT_MAGIC = b"ZKSHI1\0\0"
SCHEMA_VERSION = 1
STATEMENT_DOMAIN = b"zkTH06/openvm/player-shooting/v1\0"
VECTOR_HEADER = struct.Struct("<8sIIII4BI32s32s32s32s32s")
VECTOR_RECORD = struct.Struct("<IHBBiIIHBBii")
INPUT_HEADER = struct.Struct("<8sIIBBBB")
FINAL_STATE = struct.Struct("<IIIBB2xiH2xiiI")


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
        raise ValueError("truncated player-shooting vector")
    (
        magic,
        schema,
        header_bytes,
        record_bytes,
        source_frames,
        character,
        shot_type,
        profile_flags,
        reserved,
        anchor_game_frame,
        target_hash,
        replay_hash,
        retail_trace_hash,
        comparison_hash,
        audit_hash,
    ) = VECTOR_HEADER.unpack_from(vector)
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported player-shooting vector")
    if header_bytes != VECTOR_HEADER.size or record_bytes != VECTOR_RECORD.size:
        raise ValueError("unexpected player-shooting vector layout")
    if profile_flags != 0 or reserved != 0 or anchor_game_frame != 1:
        raise ValueError("unsupported player-shooting profile")
    if len(vector) != header_bytes + source_frames * record_bytes:
        raise ValueError("player-shooting vector size does not match its header")
    available = source_frames - 1
    count = available if args.transitions is None else args.transitions
    if not 1 <= count <= available:
        raise ValueError(f"transitions must be in 1..{available}")

    records = [
        VECTOR_RECORD.unpack_from(vector, header_bytes + index * record_bytes)
        for index in range(count + 1)
    ]
    first = records[0]
    if first != (0, 0, 3, 0, 239, 0x43400000, 0x43C00000, 0, 0xFF, 0, -999, -1):
        raise ValueError("vector does not begin at the fixed shooting anchor")

    payload = bytearray(
        INPUT_HEADER.pack(
            INPUT_MAGIC,
            SCHEMA_VERSION,
            count,
            character,
            shot_type,
            profile_flags,
            reserved,
        )
    )
    spawn_call_count = 0
    fire_previous, fire_current = first[10], first[11]
    previous_life, previous_life_timer = first[2], first[4]
    for index, record in enumerate(records[1:], 1):
        (
            frame_index,
            input_mask,
            life_state,
            flags,
            life_timer,
            _x_bits,
            _y_bits,
            previous_input,
            spawn_timer,
            record_reserved,
            observed_fire_previous,
            observed_fire_current,
        ) = record
        if frame_index != index:
            raise ValueError(f"non-contiguous frame index {frame_index}")
        if input_mask & 0x0002 or flags & 0x0B or record_reserved != 0:
            raise ValueError(f"frame {frame_index} leaves the closed profile")
        if previous_input != input_mask or bool(flags & 4) != bool(input_mask & 4):
            raise ValueError(f"input-derived Player field mismatch at frame {frame_index}")

        if previous_life == 3:
            expected_life_timer = previous_life_timer - 1
            expected_life = 0 if expected_life_timer == 0 else 3
        elif previous_life == 0:
            expected_life_timer = previous_life_timer + 1
            expected_life = 0
        else:
            raise ValueError(f"unsupported preceding life state at frame {frame_index}")
        if (life_state, life_timer) != (expected_life, expected_life_timer):
            raise ValueError(f"life-state recurrence mismatch at frame {frame_index}")

        if fire_current < 0 and input_mask & 1:
            fire_previous, fire_current = -999, 0
        expected_spawn = 0xFF
        if fire_current >= 0:
            if fire_current != fire_previous:
                expected_spawn = fire_current
                spawn_call_count += 1
            fire_previous = fire_current
            fire_current += 1
            if fire_current >= 30:
                fire_previous, fire_current = -999, -1
        if spawn_timer != expected_spawn:
            raise ValueError(f"SpawnBullets recurrence mismatch at frame {frame_index}")
        if (observed_fire_previous, observed_fire_current) != (fire_previous, fire_current):
            raise ValueError(f"fire-timer recurrence mismatch at frame {frame_index}")

        payload.extend(struct.pack("<H", input_mask))
        previous_life, previous_life_timer = life_state, life_timer

    final = records[-1]
    final_state = FINAL_STATE.pack(
        final[0] + anchor_game_frame,
        final[5],
        final[6],
        final[2],
        final[3] & 0x07,
        final[4],
        final[7],
        final[10],
        final[11],
        spawn_call_count,
    )
    statement_digest = hashlib.sha256(STATEMENT_DOMAIN + payload + final_state).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-player-shooting-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "transitions": count,
        "character": character,
        "shot_type": shot_type,
        "profile": "full-speed-no-dialogue-no-bomb-no-hit-no-time-stop-write",
        "target_executable_sha256": target_hash.hex(),
        "replay_sha256": replay_hash.hex(),
        "retail_trace_sha256": retail_trace_hash.hex(),
        "comparison_sha256": comparison_hash.hex(),
        "static_audit_sha256": audit_hash.hex(),
        "expected_final_game_frame": final[0] + anchor_game_frame,
        "expected_final_x_bits": final[5],
        "expected_final_y_bits": final[6],
        "expected_final_player_state": final[2],
        "expected_final_flags": final[3] & 0x07,
        "expected_final_invulnerability_timer": final[4],
        "expected_final_previous_frame_input": final[7],
        "expected_final_fire_timer_previous": final[10],
        "expected_final_fire_timer_current": final[11],
        "expected_final_spawn_call_count": spawn_call_count,
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "hash-bound closed Player state through SpawnBullets cadence with per-frame replay "
            "input only; excludes bullet allocation/geometry, dialogue, bomb, hit/death, respawn, "
            "and ECL time-stop writes"
        ),
    }
    report_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "/home/" in report_text:
        raise AssertionError("report contains a local absolute path")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "built",
                "transitions": count,
                "spawn_calls": spawn_call_count,
                "input_payload_bytes": len(payload),
                "expected_statement_sha256": statement_digest.hex(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

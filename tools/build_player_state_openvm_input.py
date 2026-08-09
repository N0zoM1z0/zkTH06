#!/usr/bin/env python3
"""Convert a closed player-state vector into an OpenVM private input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKPSV1\0\0"
INPUT_MAGIC = b"ZKPSI1\0\0"
SCHEMA_VERSION = 1
STATEMENT_DOMAIN = b"zkTH06/openvm/player-state/v1\0"
VECTOR_HEADER = struct.Struct("<8sIIII4BI32s32s32s32s")
VECTOR_RECORD = struct.Struct("<IHBBiII")
INPUT_HEADER = struct.Struct("<8sIIBBBB")
FINAL_STATE = struct.Struct("<IIIBB2xi")


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
        raise ValueError("truncated player-state vector")
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
    ) = VECTOR_HEADER.unpack_from(vector)
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported player-state vector")
    if header_bytes != VECTOR_HEADER.size or record_bytes != VECTOR_RECORD.size:
        raise ValueError("unexpected player-state vector layout")
    if profile_flags != 0 or reserved != 0 or anchor_game_frame != 1:
        raise ValueError("unsupported player-state profile")
    if len(vector) != header_bytes + source_frames * record_bytes:
        raise ValueError("player-state vector size does not match its header")
    available = source_frames - 1
    count = available if args.transitions is None else args.transitions
    if not 1 <= count <= available:
        raise ValueError(f"transitions must be in 1..{available}")

    records = [
        VECTOR_RECORD.unpack_from(vector, header_bytes + index * record_bytes)
        for index in range(count + 1)
    ]
    first = records[0]
    if first[0] != 0 or first[2:] != (3, 0, 239, 0x43400000, 0x43C00000):
        raise ValueError("vector does not begin at the fixed retail anchor")

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
    previous_state = first[2]
    previous_timer = first[4]
    for index, record in enumerate(records[1:], 1):
        frame_index, input_mask, state, flags, timer, _, _ = record
        if frame_index != index:
            raise ValueError(f"non-contiguous frame index {frame_index}")
        if input_mask & 0x0002 or flags != 0:
            raise ValueError(f"frame {frame_index} leaves the closed profile")
        if previous_state == 3:
            expected_timer = previous_timer - 1
            expected_state = 0 if expected_timer == 0 else 3
        else:
            expected_timer = previous_timer + 1
            expected_state = 0
        if (state, timer) != (expected_state, expected_timer):
            raise ValueError(f"life-state recurrence mismatch at frame {frame_index}")
        payload.extend(struct.pack("<H", input_mask))
        previous_state, previous_timer = state, timer

    final = records[-1]
    final_state = FINAL_STATE.pack(
        final[0] + anchor_game_frame,
        final[5],
        final[6],
        final[2],
        final[3],
        final[4],
    )
    statement_digest = hashlib.sha256(STATEMENT_DOMAIN + payload + final_state).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-player-state-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "transitions": count,
        "character": character,
        "shot_type": shot_type,
        "profile": "full-speed-no-bomb-no-hit-no-time-stop-write",
        "target_executable_sha256": target_hash.hex(),
        "replay_sha256": replay_hash.hex(),
        "retail_trace_sha256": retail_trace_hash.hex(),
        "comparison_sha256": comparison_hash.hex(),
        "expected_final_game_frame": final[0] + anchor_game_frame,
        "expected_final_x_bits": final[5],
        "expected_final_y_bits": final[6],
        "expected_final_player_state": final[2],
        "expected_final_flags": final[3],
        "expected_final_invulnerability_timer": final[4],
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "hash-bound closed player-position/life-timer profile with per-frame replay "
            "input only; excludes bomb, hit/death, respawn, and ECL time-stop writes"
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
                "input_payload_bytes": len(payload),
                "expected_statement_sha256": statement_digest.hex(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Convert the local Player bullet-spawn vector into an OpenVM private input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKPBV1\0\0"
INPUT_MAGIC = b"ZKPBI1\0\0"
SCHEMA_VERSION = 1
STATEMENT_DOMAIN = b"zkTH06/openvm/player-bullets/v1\0"
OUTPUT_DOMAIN = b"zkTH06/player-bullets/output/v1\0"
VECTOR_HEADER = struct.Struct("<8s6I4B2I32s32s32s32s32s20x")
VECTOR_PREFIX = struct.Struct("<IH4B9I80B2x")
VECTOR_ALLOCATION = struct.Struct("<4BhH12IiIi2h")
INPUT_HEADER = struct.Struct("<8sII4B")
INPUT_RECORD = struct.Struct("<IHBB9I80B")
SUMMARY = struct.Struct("<8I4B32s")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vector", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--calls", type=int)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vector = args.vector.read_bytes()
    if len(vector) < VECTOR_HEADER.size:
        raise ValueError("truncated player-bullet vector")
    (
        magic,
        schema,
        header_bytes,
        record_bytes,
        source_frames,
        spawn_calls,
        initialized_bullets,
        character,
        shot_type,
        maximum_rank,
        profile_flags,
        first_game_frame,
        last_game_frame,
        retail_trace_hash,
        reference_trace_hash,
        comparison_hash,
        audit_hash,
        generator_hash,
    ) = VECTOR_HEADER.unpack_from(vector)
    expected_record_bytes = VECTOR_PREFIX.size + 4 * VECTOR_ALLOCATION.size
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported player-bullet vector")
    if header_bytes != VECTOR_HEADER.size or record_bytes != expected_record_bytes:
        raise ValueError("unexpected player-bullet vector layout")
    if (character, shot_type, maximum_rank, profile_flags) != (0, 0, 3, 1):
        raise ValueError("unsupported player-bullet vector profile")
    if len(vector) != header_bytes + spawn_calls * record_bytes:
        raise ValueError("player-bullet vector size does not match its header")
    count = spawn_calls if args.calls is None else args.calls
    if not 1 <= count <= spawn_calls:
        raise ValueError(f"calls must be in 1..{spawn_calls}")

    payload = bytearray(
        INPUT_HEADER.pack(
            INPUT_MAGIC,
            SCHEMA_VERSION,
            count,
            character,
            shot_type,
            maximum_rank,
            profile_flags,
        )
    )
    output_digest = hashlib.sha256(OUTPUT_DOMAIN)
    rank_calls = [0, 0, 0]
    selected_allocations = 0
    zero_allocation_calls = 0
    maximum_active = 0
    selected_last_frame = 0
    for record_index in range(count):
        offset = header_bytes + record_index * record_bytes
        prefix = VECTOR_PREFIX.unpack_from(vector, offset)
        (
            game_frame,
            power,
            timer,
            focus,
            allocation_count,
            reserved,
            *tail,
        ) = prefix
        if reserved != 0 or allocation_count > 4:
            raise ValueError(f"invalid vector record {record_index}")
        positions = tail[:9]
        states = tail[9:]
        if len(states) != 80 or any(state > 2 for state in states):
            raise ValueError(f"invalid slot states at vector record {record_index}")
        if record_index and game_frame <= selected_last_frame:
            raise ValueError("spawn records are not strictly ordered")
        selected_last_frame = game_frame
        rank_index = 0 if power < 8 else 1 if power < 16 else 2 if power < 32 else -1
        if rank_index < 0:
            raise ValueError(f"unsupported power at vector record {record_index}")
        rank_calls[rank_index] += 1
        selected_allocations += allocation_count
        zero_allocation_calls += allocation_count == 0
        maximum_active = max(maximum_active, sum(state != 0 for state in states))
        payload.extend(
            INPUT_RECORD.pack(
                game_frame,
                power,
                timer,
                focus,
                *positions,
                *states,
            )
        )
        output_digest.update(struct.pack("<IB", game_frame, allocation_count))
        allocation_offset = offset + VECTOR_PREFIX.size
        for allocation_index in range(4):
            allocation = vector[
                allocation_offset + allocation_index * VECTOR_ALLOCATION.size :
                allocation_offset + (allocation_index + 1) * VECTOR_ALLOCATION.size
            ]
            if allocation_index < allocation_count:
                output_digest.update(allocation)
            elif any(allocation):
                raise ValueError(f"nonzero padded allocation at vector record {record_index}")

    geometry_digest = output_digest.digest()
    summary = SUMMARY.pack(
        selected_last_frame,
        count,
        selected_allocations,
        rank_calls[0],
        rank_calls[1],
        rank_calls[2],
        zero_allocation_calls,
        maximum_active,
        character,
        shot_type,
        maximum_rank,
        profile_flags,
        geometry_digest,
    )
    statement_digest = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-player-bullets-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "source_frames": source_frames,
        "available_spawn_calls": spawn_calls,
        "available_initialized_bullets": initialized_bullets,
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "spawn_calls": count,
        "initialized_bullets": selected_allocations,
        "first_available_game_frame": first_game_frame,
        "last_available_game_frame": last_game_frame,
        "selected_last_game_frame": selected_last_frame,
        "rank_call_counts": {"1": rank_calls[0], "2": rank_calls[1], "3": rank_calls[2]},
        "zero_allocation_calls": zero_allocation_calls,
        "maximum_pre_call_active_slots": maximum_active,
        "character": character,
        "shot_type": shot_type,
        "maximum_rank": maximum_rank,
        "profile_flags": profile_flags,
        "retail_trace_sha256": retail_trace_hash.hex(),
        "reference_trace_sha256": reference_trace_hash.hex(),
        "comparison_sha256": comparison_hash.hex(),
        "static_audit_sha256": audit_hash.hex(),
        "vector_generator_sha256": generator_hash.hex(),
        "expected_geometry_sha256": geometry_digest.hex(),
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "output_domain_ascii": OUTPUT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "hash-bound batch of independently observed Reimu-A SpawnBullets pre-states; proves local "
            "allocation and geometry for each call but does not link slots across calls through bullet "
            "motion, ANM termination, or Enemy collision"
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
                "spawn_calls": count,
                "initialized_bullets": selected_allocations,
                "input_payload_bytes": len(payload),
                "expected_statement_sha256": statement_digest.hex(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

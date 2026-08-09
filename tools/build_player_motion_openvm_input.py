#!/usr/bin/env python3
"""Convert a committed retail vector into a private OpenVM batch input."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


VECTOR_MAGIC = b"ZKPMV1\0\0"
INPUT_MAGIC = b"ZKPMI1\0\0"
SCHEMA_VERSION = 1
STATEMENT_DOMAIN = b"zkTH06/openvm/player-motion/v1\0"
VECTOR_HEADER = struct.Struct("<8sIIII32s32s32s")
VECTOR_RECORD = struct.Struct("<IHBB15I")
INPUT_HEADER = struct.Struct("<8sIIII")
INPUT_RECORD = struct.Struct("<HBB11I")


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
        raise ValueError("truncated player-motion vector")
    (
        magic,
        schema,
        header_bytes,
        record_bytes,
        source_frames,
        target_hash,
        replay_hash,
        retail_trace_hash,
    ) = VECTOR_HEADER.unpack_from(vector)
    if magic != VECTOR_MAGIC or schema != SCHEMA_VERSION:
        raise ValueError("unsupported player-motion vector")
    if header_bytes != VECTOR_HEADER.size or record_bytes != VECTOR_RECORD.size:
        raise ValueError("unexpected player-motion vector layout")
    available = source_frames - 1
    if len(vector) != header_bytes + available * record_bytes:
        raise ValueError("player-motion vector size does not match its header")
    count = available if args.transitions is None else args.transitions
    if not 1 <= count <= available:
        raise ValueError(f"transitions must be in 1..{available}")

    records = [
        VECTOR_RECORD.unpack_from(vector, header_bytes + index * record_bytes)
        for index in range(count)
    ]
    first = records[0]
    initial_x, initial_y = first[15], first[16]
    payload = bytearray(
        INPUT_HEADER.pack(INPUT_MAGIC, SCHEMA_VERSION, count, initial_x, initial_y)
    )
    prior_expected = None
    for offset, record in enumerate(records):
        frame_index, input_mask, player_state, flags = record[:4]
        environment = record[4:15]
        previous = record[15:17]
        expected = record[17:19]
        if frame_index != offset + 1:
            raise ValueError(f"non-contiguous frame index {frame_index}")
        if prior_expected is not None and previous != prior_expected:
            raise ValueError(f"discontinuous position at frame {frame_index}")
        if flags & ~1:
            raise ValueError(f"unsupported flags at frame {frame_index}")
        payload.extend(INPUT_RECORD.pack(input_mask, player_state, flags, *environment))
        prior_expected = expected

    assert prior_expected is not None
    final_x, final_y = prior_expected
    statement_digest = hashlib.sha256(
        STATEMENT_DOMAIN + payload + struct.pack("<II", final_x, final_y)
    ).digest()
    input_document = {"input": ["0x01" + payload.hex()]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(input_document, separators=(",", ":")) + "\n", encoding="utf-8")

    report = {
        "type": "zkth06.openvm-player-motion-input",
        "schema_version": SCHEMA_VERSION,
        "source_vector_sha256": sha256(vector),
        "input_payload_sha256": sha256(payload),
        "input_payload_bytes": len(payload),
        "transitions": count,
        "target_executable_sha256": target_hash.hex(),
        "replay_sha256": replay_hash.hex(),
        "retail_trace_sha256": retail_trace_hash.hex(),
        "expected_final_x_bits": final_x,
        "expected_final_y_bits": final_y,
        "statement_domain_ascii": STATEMENT_DOMAIN.rstrip(b"\0").decode("ascii"),
        "expected_statement_sha256": statement_digest.hex(),
        "expected_public_u32": list(struct.unpack("<8I", statement_digest)),
        "claim_boundary": (
            "hash-bound backend workload derived from finite retail vectors; environment "
            "remains private and unconstrained by a complete TH06 transition"
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
                "expected_final_x_bits": final_x,
                "expected_final_y_bits": final_y,
                "expected_statement_sha256": statement_digest.hex(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

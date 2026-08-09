#!/usr/bin/env python3
"""Build a compact player-motion vector from a sealed retail anchor trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


MAGIC = b"ZKPMV1\0\0"
SCHEMA_VERSION = 1
HEADER = struct.Struct("<8sIIII32s32s32s")
RECORD = struct.Struct("<IHBB15I")
FRAME_TYPE = "zkth06.retail-anchor-frame"
HEADER_TYPE = "zkth06.retail-anchor-header"

RAW_FIELDS = (
    "effective_rate_bits",
    "movement_min_x_bits",
    "movement_min_y_bits",
    "movement_size_x_bits",
    "movement_size_y_bits",
    "horizontal_multiplier_bits",
    "vertical_multiplier_bits",
    "orthogonal_speed_bits",
    "orthogonal_focus_speed_bits",
    "diagonal_speed_bits",
    "diagonal_focus_speed_bits",
    "player_x_bits",
    "player_y_bits",
)
REQUIRED_COMPARISON_FIELDS = set(RAW_FIELDS) | {
    "input",
    "is_time_stopped",
    "player_state",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_u32(value: Any) -> int:
    parsed = int(value, 0) if isinstance(value, str) else int(value)
    if not 0 <= parsed <= 0xFFFF_FFFF:
        raise ValueError(f"raw value outside u32: {value!r}")
    return parsed


def read_trace(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    trace_bytes = path.read_bytes()
    rows = [json.loads(line) for line in trace_bytes.splitlines() if line.strip()]
    if not rows or rows[0].get("type") != HEADER_TYPE:
        raise ValueError("retail trace header is missing or invalid")
    frames = rows[1:]
    if len(frames) < 2:
        raise ValueError("at least two retail frames are required")
    for index, frame in enumerate(frames):
        if frame.get("type") != FRAME_TYPE or int(frame.get("index", -1)) != index:
            raise ValueError(f"invalid or non-contiguous retail frame at index {index}")
        for field in RAW_FIELDS:
            raw_u32(frame[field])
        if int(frame["player_state"]) not in (0, 3) and not int(frame["is_time_stopped"]):
            raise ValueError(f"frame {index} is outside the motion slice's player-state domain")
        if frame["x87_control_word"] != "0x007f":
            raise ValueError(f"frame {index} does not use the observed PC24 x87 profile")
    return rows[0], frames, trace_bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trace_header, frames, trace_bytes = read_trace(args.retail_trace)
    trace_sha256 = sha256_bytes(trace_bytes)
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    if comparison.get("status") != "match":
        raise ValueError("retail/reference comparison did not match")
    if int(comparison.get("compared_frames", -1)) != len(frames):
        raise ValueError("comparison and retail trace frame counts differ")
    missing_fields = REQUIRED_COMPARISON_FIELDS - set(comparison.get("compared_fields", ()))
    if missing_fields:
        raise ValueError(
            "comparison does not cover the motion vector fields: "
            + ", ".join(sorted(missing_fields))
        )
    if comparison.get("retail_trace_sha256") != trace_sha256:
        raise ValueError("comparison is not bound to the supplied retail trace")

    target_sha256 = str(trace_header["target_executable_sha256"])
    replay_sha256 = str(trace_header["replay_sha256"])
    if comparison.get("target_executable_sha256") != target_sha256:
        raise ValueError("comparison target hash differs from the retail trace")
    if comparison.get("replay_sha256") != replay_sha256:
        raise ValueError("comparison replay hash differs from the retail trace")

    transition_count = len(frames) - 1
    vector = bytearray(
        HEADER.pack(
            MAGIC,
            SCHEMA_VERSION,
            HEADER.size,
            RECORD.size,
            len(frames),
            bytes.fromhex(target_sha256),
            bytes.fromhex(replay_sha256),
            bytes.fromhex(trace_sha256),
        )
    )
    for index in range(1, len(frames)):
        previous = frames[index - 1]
        current = frames[index]
        flags = int(bool(int(current["is_time_stopped"])))
        vector.extend(
            RECORD.pack(
                index,
                int(current["input"]),
                int(current["player_state"]),
                flags,
                raw_u32(current["effective_rate_bits"]),
                raw_u32(current["movement_min_x_bits"]),
                raw_u32(current["movement_min_y_bits"]),
                raw_u32(current["movement_size_x_bits"]),
                raw_u32(current["movement_size_y_bits"]),
                raw_u32(current["horizontal_multiplier_bits"]),
                raw_u32(current["vertical_multiplier_bits"]),
                raw_u32(current["orthogonal_speed_bits"]),
                raw_u32(current["orthogonal_focus_speed_bits"]),
                raw_u32(current["diagonal_speed_bits"]),
                raw_u32(current["diagonal_focus_speed_bits"]),
                raw_u32(previous["player_x_bits"]),
                raw_u32(previous["player_y_bits"]),
                raw_u32(current["player_x_bits"]),
                raw_u32(current["player_y_bits"]),
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(vector)
    manifest = {
        "type": "zkth06.player-motion-vector",
        "schema_version": SCHEMA_VERSION,
        "format": "little-endian ZKPMV1",
        "header_bytes": HEADER.size,
        "record_bytes": RECORD.size,
        "source_frames": len(frames),
        "tested_transitions": transition_count,
        "first_transition_index": 1,
        "last_transition_index": len(frames) - 1,
        "target_executable_sha256": target_sha256,
        "replay_sha256": replay_sha256,
        "retail_trace_sha256": trace_sha256,
        "reference_trace_sha256": comparison["reference_trace_sha256"],
        "vector_sha256": sha256_bytes(vector),
        "x87_control_words": comparison["retail_x87_control_words"],
        "comparison_artifact": "retail-reference-002677-2000-v1.json",
        "claim_boundary": (
            "retail-derived consecutive player-position test vectors over one replay prefix; "
            "not a proof of arithmetic, source binding, whole-player, or whole-game equivalence"
        ),
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if "/home/" in manifest_text:
        raise AssertionError("manifest contains a local absolute path")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(manifest_text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "built",
                "source_frames": len(frames),
                "tested_transitions": transition_count,
                "vector_sha256": manifest["vector_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

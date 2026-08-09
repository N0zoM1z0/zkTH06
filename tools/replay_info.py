#!/usr/bin/env python3
"""Inspect and validate Touhou 6 (v1.02h) replay files.

The format and byte transform are implemented from ReplayData.hpp and
ReplayManager.cpp in GensokyoClub/th06.  This utility deliberately reports the
per-stage snapshots stored in the file; those snapshots are inputs supplied by
the replay and are not evidence that the preceding stage derived them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


HEADER_SIZE = 0x50
STAGE_HEADER_SIZE = 0x10
INPUT_RECORD_SIZE = 0x08
CHECKSUM_SEED = 0x3F000318
EXPECTED_MAGIC = b"T6RP"
EXPECTED_VERSION = 0x0102
REPLAY_END_FRAME = 9_999_999
REPLAY_INPUT_MASK = 0x01F7


class ReplayError(ValueError):
    pass


def _cstring(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("cp932", errors="replace")


def _deobfuscate(raw: bytes) -> bytearray:
    if len(raw) < HEADER_SIZE:
        raise ReplayError(f"file is too short: {len(raw)} bytes")
    if raw[:4] != EXPECTED_MAGIC:
        raise ReplayError(f"bad magic: {raw[:4]!r}")

    decoded = bytearray(raw)
    offset = decoded[14]
    for cursor in range(15, len(decoded)):
        decoded[cursor] = (decoded[cursor] - offset) & 0xFF
        offset = (offset + 7) & 0xFF
    return decoded


def inspect_replay(path: Path, include_inputs: bool = False) -> dict[str, Any]:
    raw = path.read_bytes()
    data = _deobfuscate(raw)

    version = struct.unpack_from("<H", data, 4)[0]
    stored_checksum = struct.unpack_from("<I", data, 8)[0]
    calculated_checksum = (CHECKSUM_SEED + sum(data[14:])) & 0xFFFFFFFF
    stage_offsets = list(struct.unpack_from("<7I", data, 52))

    if stored_checksum != calculated_checksum:
        raise ReplayError(
            f"checksum mismatch: expected 0x{stored_checksum:08x}, "
            f"calculated 0x{calculated_checksum:08x}"
        )
    if version != EXPECTED_VERSION:
        raise ReplayError(f"unsupported replay version: 0x{version:04x}")
    if data[6] > 3:
        raise ReplayError(f"invalid character/shot index: {data[6]}")
    if data[7] > 4:
        raise ReplayError(f"invalid difficulty: {data[7]}")

    nonzero_offsets = [offset for offset in stage_offsets if offset]
    if not nonzero_offsets:
        raise ReplayError("replay contains no stage data")
    if any(offset < HEADER_SIZE or offset >= len(data) for offset in nonzero_offsets):
        raise ReplayError(f"stage offset lies outside file: {stage_offsets}")
    if any(offset % INPUT_RECORD_SIZE for offset in nonzero_offsets):
        raise ReplayError(f"stage offset is not {INPUT_RECORD_SIZE}-byte aligned: {stage_offsets}")
    if nonzero_offsets != sorted(nonzero_offsets) or len(nonzero_offsets) != len(set(nonzero_offsets)):
        raise ReplayError(f"stage offsets are not strictly increasing: {stage_offsets}")

    result: dict[str, Any] = {
        "path": str(path),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "magic": data[:4].decode("ascii"),
        "version": f"0x{version:04x}",
        "version_supported": True,
        "checksum": {
            "stored": f"0x{stored_checksum:08x}",
            "calculated": f"0x{calculated_checksum:08x}",
            "valid": True,
        },
        "valid": True,
        "shot_type_character": data[6],
        "character": data[6] // 2,
        "shot_type": data[6] % 2,
        "difficulty": data[7],
        "date": _cstring(bytes(data[16:25])),
        "name": _cstring(bytes(data[25:33])),
        "score": struct.unpack_from("<i", data, 36)[0],
        "slowdown_rates": list(struct.unpack_from("<3f", data, 40)),
        "stage_offsets": stage_offsets,
        "stages": [],
    }

    for index, start in enumerate(stage_offsets):
        if start == 0:
            continue
        later = [offset for offset in nonzero_offsets if offset > start]
        end = min(later) if later else len(data)
        stage_size = end - start
        if (
            stage_size < STAGE_HEADER_SIZE + 2 * INPUT_RECORD_SIZE
            or (stage_size - STAGE_HEADER_SIZE) % INPUT_RECORD_SIZE
        ):
            raise ReplayError(f"stage {index + 1} has invalid size {stage_size}")

        stage_end_score, seed, points = struct.unpack_from("<ihh", data, start)
        power = data[start + 8]
        lives = struct.unpack_from("<b", data, start + 9)[0]
        bombs = struct.unpack_from("<b", data, start + 10)[0]
        rank = data[start + 11]
        power_items = struct.unpack_from("<b", data, start + 12)[0]

        inputs = []
        for cursor in range(start + STAGE_HEADER_SIZE, end, INPUT_RECORD_SIZE):
            frame, mask, padding = struct.unpack_from("<iHH", data, cursor)
            inputs.append({"frame": frame, "mask": mask, "padding": padding})

        if inputs[0]["frame"] != 0:
            raise ReplayError(f"stage {index + 1} does not start with frame 0")
        previous_frame = inputs[0]["frame"]
        playback_records = 0
        terminal_frame = 0
        for record, replay_input in enumerate(inputs):
            frame = replay_input["frame"]
            mask = replay_input["mask"]
            if mask & ~REPLAY_INPUT_MASK:
                raise ReplayError(
                    f"stage {index + 1} record {record} has invalid input mask 0x{mask:04x}"
                )
            if frame == REPLAY_END_FRAME:
                if mask != 0 or record == 0:
                    raise ReplayError(f"stage {index + 1} has malformed end sentinel")
                playback_records = record + 1
                terminal_frame = inputs[record - 1]["frame"]
                break
            if frame < 0 or frame < previous_frame:
                raise ReplayError(f"stage {index + 1} input frames regress at record {record}")
            previous_frame = frame
        if playback_records == 0:
            raise ReplayError(f"stage {index + 1} has no playback end sentinel")

        stage: dict[str, Any] = {
            "stage": index + 1,
            "offset": start,
            "size": stage_size,
            # The score field is written when this stage ends.  Playback of the
            # following stage restores it from the preceding stage block.
            "stage_end_score": stage_end_score,
            "stage_start_snapshot": {
                "random_seed_signed": seed,
                "random_seed_u16": seed & 0xFFFF,
                "point_items_collected": points,
                "power": power,
                "lives_remaining": lives,
                "bombs_remaining": bombs,
                "rank": rank,
                "power_item_count_for_score": power_items,
            },
            "input_change_records": len(inputs),
            "playback_records": playback_records,
            "terminal_frame": terminal_frame,
            "first_input": inputs[0] if inputs else None,
            "last_input": inputs[-1] if inputs else None,
        }
        if include_inputs:
            stage["inputs"] = inputs
        result["stages"].append(stage)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--inputs", action="store_true", help="include every input-change record")
    args = parser.parse_args()

    reports = []
    failed = False
    for replay in args.replays:
        try:
            report = inspect_replay(replay, include_inputs=args.inputs)
            reports.append(report)
            failed = failed or not report["valid"]
        except (OSError, ReplayError) as exc:
            failed = True
            reports.append({"path": str(replay), "error": str(exc)})
    json.dump(reports[0] if len(reports) == 1 else reports, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

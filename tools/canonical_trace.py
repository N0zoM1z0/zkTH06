#!/usr/bin/env python3
"""Decode, validate, and compare zkTH06 canonical digest traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


MAGIC = b"ZKTH06CT"
VERSION = (0, 2)
HEADER_SIZE = 64
RECORD_PREFIX_SIZE = 32
SUBSYSTEM_RECORD_SIZE = 48
SUBSYSTEM_NAMES = (
    "global",
    "rng",
    "player",
    "player-bullets",
    "enemies-ecl",
    "enemy-bullets",
    "lasers",
    "items",
    "stage",
    "gui-message",
    "effects",
)
SUBSYSTEM_COUNT = len(SUBSYSTEM_NAMES)
RECORD_SIZE = RECORD_PREFIX_SIZE + SUBSYSTEM_COUNT * SUBSYSTEM_RECORD_SIZE + 32
HEADER_FLAG_SELECTED_FIELDS = 1
SUBSYSTEM_FLAG_SELECTED_FIELDS = 1
SCHEMA_DESCRIPTOR = (
    b"zkTH06 canonical trace schema 0.2\n"
    b"wire=little-endian;float=ieee754-binary32-raw-bits;coverage=selected-fields\n"
    b"projection=runtime-selected-gameplay-v0.2;stable-slots=true;relative-script-offsets=true;anm-future-live=true\n"
    b"subsystems=global,rng,player,player-bullets,enemies-ecl,enemy-bullets,lasers,items,stage,gui-message,effects\n"
    b"subsystem-digest=sha256(zkTH06-state-v0.2\\0||subsystem-u16-le||payload)\n"
    b"record-root=sha256(zkTH06-trace-root-v0.2\\0||record-prefix||subsystem-records)\n"
)
SCHEMA_DIGEST = hashlib.sha256(SCHEMA_DESCRIPTOR).digest()
ROOT_DOMAIN = b"zkTH06-trace-root-v0.2\0"

HEADER_STRUCT = struct.Struct("<8sHHIIHHH6B32s")
RECORD_PREFIX_STRUCT = struct.Struct("<QIiHBBiQ")
SUBSYSTEM_STRUCT = struct.Struct("<HHIQ32s")

RUN_MODES = {0: "unknown", 1: "practice", 2: "replay"}
TERMINAL_REASONS = {
    0: None,
    1: "input-error",
    2: "physical-hit",
    3: "replay-complete",
    4: "chain-exit-success",
    5: "chain-exit-error",
    6: "tick-limit",
    255: "unknown",
}


class CanonicalTraceError(ValueError):
    """Raised when a canonical trace violates its wire-format contract."""


@dataclass(frozen=True)
class TraceHeader:
    initial_seed: int
    difficulty: int
    character: int
    shot_type: int
    start_stage: int
    run_mode: int
    flags: int
    schema_digest: bytes

    def as_dict(self) -> dict[str, object]:
        return {
            "version": f"{VERSION[0]}.{VERSION[1]}",
            "initial_seed": self.initial_seed,
            "difficulty": self.difficulty,
            "character": self.character,
            "shot_type": self.shot_type,
            "start_stage": self.start_stage,
            "run_mode": RUN_MODES[self.run_mode],
            "coverage": "selected-fields",
            "schema_sha256": self.schema_digest.hex(),
            "record_size": RECORD_SIZE,
            "subsystems": list(SUBSYSTEM_NAMES),
        }


@dataclass(frozen=True)
class SubsystemDigest:
    subsystem_id: int
    flags: int
    entity_count: int
    byte_count: int
    digest: bytes

    @property
    def name(self) -> str:
        return SUBSYSTEM_NAMES[self.subsystem_id - 1]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.subsystem_id,
            "name": self.name,
            "coverage": "selected-fields",
            "entity_count": self.entity_count,
            "byte_count": self.byte_count,
            "sha256": self.digest.hex(),
        }


@dataclass(frozen=True)
class FrameRecord:
    tick: int
    game_frame: int
    stage: int
    input_mask: int
    terminal_reason: int
    flags: int
    supervisor_state: int
    record_index: int
    subsystems: tuple[SubsystemDigest, ...]
    root_digest: bytes

    def as_dict(self, include_subsystems: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "record_index": self.record_index,
            "tick": self.tick,
            "game_frame": self.game_frame,
            "stage": self.stage,
            "input": self.input_mask,
            "terminal_reason": TERMINAL_REASONS[self.terminal_reason],
            "flags": self.flags,
            "supervisor_state": self.supervisor_state,
            "root_sha256": self.root_digest.hex(),
        }
        if include_subsystems:
            result["subsystems"] = [subsystem.as_dict() for subsystem in self.subsystems]
        return result


def _read_exact(file: BinaryIO, size: int, what: str) -> bytes:
    data = file.read(size)
    if len(data) != size:
        raise CanonicalTraceError(f"truncated {what}: expected {size} bytes, got {len(data)}")
    return data


def read_header(file: BinaryIO) -> TraceHeader:
    raw = _read_exact(file, HEADER_SIZE, "canonical trace header")
    (
        magic,
        major,
        minor,
        header_size,
        record_size,
        subsystem_count,
        flags,
        initial_seed,
        difficulty,
        character,
        shot_type,
        start_stage,
        run_mode,
        reserved,
        schema_digest,
    ) = HEADER_STRUCT.unpack(raw)
    if magic != MAGIC:
        raise CanonicalTraceError(f"invalid canonical trace magic: {magic!r}")
    if (major, minor) != VERSION:
        raise CanonicalTraceError(f"unsupported canonical trace version: {major}.{minor}")
    if header_size != HEADER_SIZE:
        raise CanonicalTraceError(f"unexpected canonical header size: {header_size}")
    if record_size != RECORD_SIZE:
        raise CanonicalTraceError(f"unexpected canonical record size: {record_size}")
    if subsystem_count != SUBSYSTEM_COUNT:
        raise CanonicalTraceError(f"unexpected canonical subsystem count: {subsystem_count}")
    if flags != HEADER_FLAG_SELECTED_FIELDS:
        raise CanonicalTraceError(f"unsupported canonical header flags: 0x{flags:04x}")
    if reserved != 0:
        raise CanonicalTraceError("canonical header reserved byte is nonzero")
    if run_mode not in RUN_MODES:
        raise CanonicalTraceError(f"unsupported canonical run mode: {run_mode}")
    if schema_digest != SCHEMA_DIGEST:
        raise CanonicalTraceError(
            f"canonical schema mismatch: expected {SCHEMA_DIGEST.hex()}, got {schema_digest.hex()}"
        )
    return TraceHeader(
        initial_seed=initial_seed,
        difficulty=difficulty,
        character=character,
        shot_type=shot_type,
        start_stage=start_stage,
        run_mode=run_mode,
        flags=flags,
        schema_digest=schema_digest,
    )


def decode_record(raw: bytes, physical_index: int, verify_root: bool = True) -> FrameRecord:
    if len(raw) != RECORD_SIZE:
        raise CanonicalTraceError(f"record {physical_index} has {len(raw)} bytes, expected {RECORD_SIZE}")
    prefix = RECORD_PREFIX_STRUCT.unpack_from(raw, 0)
    tick, game_frame, stage, input_mask, terminal_reason, flags, supervisor_state, record_index = prefix
    if record_index != physical_index:
        raise CanonicalTraceError(
            f"record index mismatch at physical record {physical_index}: encoded {record_index}"
        )
    if terminal_reason not in TERMINAL_REASONS:
        raise CanonicalTraceError(f"record {physical_index} has unknown terminal code {terminal_reason}")

    subsystems: list[SubsystemDigest] = []
    offset = RECORD_PREFIX_SIZE
    for expected_id in range(1, SUBSYSTEM_COUNT + 1):
        subsystem_id, subsystem_flags, entity_count, byte_count, digest = SUBSYSTEM_STRUCT.unpack_from(raw, offset)
        if subsystem_id != expected_id:
            raise CanonicalTraceError(
                f"record {physical_index} subsystem order mismatch: expected {expected_id}, got {subsystem_id}"
            )
        if subsystem_flags != SUBSYSTEM_FLAG_SELECTED_FIELDS:
            raise CanonicalTraceError(
                f"record {physical_index} subsystem {subsystem_id} has unsupported flags 0x{subsystem_flags:04x}"
            )
        subsystems.append(
            SubsystemDigest(
                subsystem_id=subsystem_id,
                flags=subsystem_flags,
                entity_count=entity_count,
                byte_count=byte_count,
                digest=digest,
            )
        )
        offset += SUBSYSTEM_RECORD_SIZE

    root_digest = raw[-32:]
    if verify_root:
        expected_root = hashlib.sha256(ROOT_DOMAIN + raw[:-32]).digest()
        if root_digest != expected_root:
            raise CanonicalTraceError(
                f"record {physical_index} root mismatch: expected {expected_root.hex()}, got {root_digest.hex()}"
            )
    return FrameRecord(
        tick=tick,
        game_frame=game_frame,
        stage=stage,
        input_mask=input_mask,
        terminal_reason=terminal_reason,
        flags=flags,
        supervisor_state=supervisor_state,
        record_index=record_index,
        subsystems=tuple(subsystems),
        root_digest=root_digest,
    )


def iter_records(file: BinaryIO, verify_root: bool = True) -> Iterator[FrameRecord]:
    physical_index = 0
    while True:
        raw = file.read(RECORD_SIZE)
        if not raw:
            return
        if len(raw) != RECORD_SIZE:
            raise CanonicalTraceError(
                f"truncated canonical record {physical_index}: expected {RECORD_SIZE} bytes, got {len(raw)}"
            )
        yield decode_record(raw, physical_index, verify_root=verify_root)
        physical_index += 1


def read_trace(path: Path, verify_root: bool = True) -> tuple[TraceHeader, list[FrameRecord]]:
    with path.open("rb") as file:
        header = read_header(file)
        records = list(iter_records(file, verify_root=verify_root))
    return header, records


def summarize(path: Path) -> dict[str, object]:
    with path.open("rb") as file:
        header = read_header(file)
        first: FrameRecord | None = None
        last: FrameRecord | None = None
        count = 0
        total_payload_bytes = 0
        subsystem_stats = [
            {"total_bytes": 0, "min_bytes": None, "max_bytes": 0, "max_entities": 0}
            for _ in SUBSYSTEM_NAMES
        ]
        for record in iter_records(file):
            if first is None:
                first = record
            last = record
            count += 1
            for index, subsystem in enumerate(record.subsystems):
                stats = subsystem_stats[index]
                stats["total_bytes"] += subsystem.byte_count
                stats["min_bytes"] = (
                    subsystem.byte_count
                    if stats["min_bytes"] is None
                    else min(stats["min_bytes"], subsystem.byte_count)
                )
                stats["max_bytes"] = max(stats["max_bytes"], subsystem.byte_count)
                stats["max_entities"] = max(stats["max_entities"], subsystem.entity_count)
                total_payload_bytes += subsystem.byte_count
    named_stats = {
        name: {
            **stats,
            "min_bytes": 0 if stats["min_bytes"] is None else stats["min_bytes"],
        }
        for name, stats in zip(SUBSYSTEM_NAMES, subsystem_stats, strict=True)
    }
    return {
        "valid": True,
        "path": str(path),
        "size": path.stat().st_size,
        "header": header.as_dict(),
        "record_count": count,
        "hashed_payload_bytes": total_payload_bytes,
        "subsystem_stats": named_stats,
        "first_record": None if first is None else first.as_dict(include_subsystems=True),
        "last_record": None if last is None else last.as_dict(include_subsystems=True),
    }


def compare(left_path: Path, right_path: Path) -> dict[str, object]:
    with left_path.open("rb") as left_file, right_path.open("rb") as right_file:
        left_header = read_header(left_file)
        right_header = read_header(right_file)
        if left_header != right_header:
            return {
                "equal": False,
                "kind": "header",
                "left": left_header.as_dict(),
                "right": right_header.as_dict(),
            }

        left_records = iter_records(left_file)
        right_records = iter_records(right_file)
        index = 0
        while True:
            left = next(left_records, None)
            right = next(right_records, None)
            if left is None or right is None:
                if left is None and right is None:
                    return {"equal": True, "record_count": index}
                return {
                    "equal": False,
                    "kind": "length",
                    "matching_records": index,
                    "left_ended": left is None,
                    "right_ended": right is None,
                }
            if left.root_digest != right.root_digest:
                changed_subsystems = [
                    left_subsystem.name
                    for left_subsystem, right_subsystem in zip(left.subsystems, right.subsystems, strict=True)
                    if left_subsystem != right_subsystem
                ]
                return {
                    "equal": False,
                    "kind": "record",
                    "first_mismatch": index,
                    "changed_subsystems": changed_subsystems,
                    "left": left.as_dict(include_subsystems=True),
                    "right": right.as_dict(include_subsystems=True),
                }
            index += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="canonical trace to validate")
    parser.add_argument("--compare", type=Path, metavar="OTHER", help="find the first mismatch against OTHER")
    args = parser.parse_args()
    try:
        result = compare(args.trace, args.compare) if args.compare is not None else summarize(args.trace)
    except (CanonicalTraceError, OSError) as error:
        print(json.dumps({"valid": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if args.compare is None or result["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

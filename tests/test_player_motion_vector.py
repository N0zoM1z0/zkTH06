#!/usr/bin/env python3
"""Validate the committed retail-derived player-motion vector envelope."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "evidence" / "player-motion-002677-2000-v1.bin"
MANIFEST = ROOT / "evidence" / "player-motion-002677-2000-v1.json"
COMPARISON = ROOT / "evidence" / "retail-reference-002677-2000-v1.json"
HEADER = struct.Struct("<8sIIII32s32s32s")
RECORD_BYTES = 68


def main() -> int:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in manifest_text
    manifest = json.loads(manifest_text)
    comparison = json.loads(COMPARISON.read_text(encoding="utf-8"))
    vector = VECTOR.read_bytes()
    (
        magic,
        schema,
        header_bytes,
        record_bytes,
        source_frames,
        target_hash,
        replay_hash,
        retail_trace_hash,
    ) = HEADER.unpack_from(vector)

    assert magic == b"ZKPMV1\0\0"
    assert schema == manifest["schema_version"] == 1
    assert header_bytes == manifest["header_bytes"] == HEADER.size
    assert record_bytes == manifest["record_bytes"] == RECORD_BYTES
    assert source_frames == manifest["source_frames"] == 2000
    assert manifest["tested_transitions"] == source_frames - 1 == 1999
    assert len(vector) == header_bytes + manifest["tested_transitions"] * record_bytes
    assert hashlib.sha256(vector).hexdigest() == manifest["vector_sha256"]
    assert target_hash.hex() == manifest["target_executable_sha256"]
    assert replay_hash.hex() == manifest["replay_sha256"]
    assert retail_trace_hash.hex() == manifest["retail_trace_sha256"]
    assert manifest["target_executable_sha256"] == comparison["target_executable_sha256"]
    assert manifest["replay_sha256"] == comparison["replay_sha256"]
    assert manifest["retail_trace_sha256"] == comparison["retail_trace_sha256"]
    assert manifest["reference_trace_sha256"] == comparison["reference_trace_sha256"]
    assert comparison["status"] == "match"
    assert len(comparison["compared_fields"]) == 34
    print("validated 1,999 retail-derived player-position transitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

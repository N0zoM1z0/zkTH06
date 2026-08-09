#!/usr/bin/env python3
"""Test proprietary-input-free point-item probe parsing and summaries."""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_item_score_probe as probe  # noqa: E402


def bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def main() -> int:
    parsed = probe.parse_markers(
        "noise\nZKTH06_ITEM_Y 3f800000\nDEBUG2: ZKTH06_ITEM_Y c0800000\n"
    )
    assert parsed == [0x3F800000, 0xC0800000]
    summary = probe.summarize(
        [bits(-4.0), bits(127.75), bits(128.0), bits(452.0), bits(453.0), bits(math.inf)]
    )
    assert summary == {
        "collections": 6,
        "finite": 5,
        "exceptional": 1,
        "outside_candidate_bound": 1,
        "minimum": -4.0,
        "maximum": 453.0,
        "truncated_minimum": -4,
        "truncated_maximum": 453,
        "top_branch": 2,
        "position_branch": 3,
    }
    commands = probe.gdb_commands(Path("ItemManager.cpp"), Path("game-data"))
    assert commands.count("break ItemManager.cpp:") == 4
    assert commands.count(probe.MARKER) == 4
    print("validated item-score GDB marker parsing and candidate-range summaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

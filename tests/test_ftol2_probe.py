#!/usr/bin/env python3
"""Unit checks for proprietary-byte-free __ftol2 extraction/model helpers."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_ftol2_probe as probe  # noqa: E402


def synthetic_pe(payload: bytes) -> tuple[bytes, int]:
    image = bytearray(0x400)
    pe_offset = 0x80
    optional_offset = pe_offset + 24
    section_offset = optional_offset + 0xE0
    image[0x3C:0x40] = struct.pack("<I", pe_offset)
    image[pe_offset : pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<H", image, pe_offset + 6, 1)
    struct.pack_into("<H", image, pe_offset + 20, 0xE0)
    struct.pack_into("<H", image, optional_offset, 0x10B)
    struct.pack_into("<I", image, optional_offset + 28, 0x400000)
    image[section_offset : section_offset + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", image, section_offset + 8, 0x100, 0x1000, 0x100, 0x200)
    image[0x220 : 0x220 + len(payload)] = payload
    return bytes(image), 0x401020


def main() -> int:
    payload = bytes(range(32))
    image, address = synthetic_pe(payload)
    assert probe.extract_pe_range(image, address, len(payload)) == payload

    assert probe.finite_f32_to_ext80(0x00000000) == probe.ext80(0, 0, 0)
    assert probe.finite_f32_to_ext80(0x80000000) == probe.ext80(1, 0, 0)
    assert probe.finite_f32_to_ext80(0x3F800000) == probe.ext80(
        0, 0x3FFF, 0x8000000000000000
    )
    assert probe.finite_f32_to_ext80(0x00000001) == probe.ext80(
        0, 16383 - 149, 0x8000000000000000
    )

    cases = {
        probe.ext80(0, 0x3FFF, 0xC000000000000000): 1,
        probe.ext80(1, 0x3FFF, 0xC000000000000000): -1,
        probe.ext80(0, 0x401D, 0xFFFFFFFE00000000): 0x7FFFFFFF,
        probe.ext80(1, 0x403E, 0x8000000000000000): -(1 << 63),
    }
    for encoded, expected in cases.items():
        assert probe.trunc_ext80(encoded) == expected
    try:
        probe.trunc_ext80(probe.ext80(0, 0x403E, 0x8000000000000000))
    except ValueError:
        pass
    else:
        raise AssertionError("positive 2^63 must be outside the signed-i64 domain")

    generated = probe.random_inputs(1000)
    assert len(generated) == 1000
    assert all(-(1 << 63) <= probe.trunc_ext80(value) < (1 << 63) for value in generated)
    print("validated PE range extraction and exact finite ext80 truncation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

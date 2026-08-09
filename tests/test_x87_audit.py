#!/usr/bin/env python3
"""Unit checks for the mapping and instruction logic in tools/x87_audit.py."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import x87_audit  # noqa: E402


DISASSEMBLY = """
00401000 <.text>:
  401000: fld    DWORD PTR [esp+0x4]
  401004: fadd   DWORD PTR [esp+0x8]
  401008: fstp   DWORD PTR [esp+0xc]
  40100c: fsincos
  40100e: fldcw  WORD PTR [esp+0x10]
  401012: call   0x401040
  401020: fistp  DWORD PTR [esp]
  401040: fsin
  401044: addss  xmm0,xmm1
"""


def main() -> int:
    instructions = x87_audit.parse_disassembly(DISASSEMBLY)
    assert len(instructions) == 9
    assert sum(x87_audit.is_x87(instruction) for instruction in instructions) == 7
    assert sum(x87_audit.uses_xmm(instruction) for instruction in instructions) == 1

    with tempfile.TemporaryDirectory(prefix="zkth06-x87-") as directory:
        mapping = Path(directory) / "mapping.csv"
        mapping.write_text(
            "th06::First,0x401000,0x20\n"
            "th06::Second,0x401020,0x10\n"
            "helper_sin,0x401040,0x10\n"
        )
        functions = x87_audit.load_mapping(mapping)
        result = x87_audit.audit(instructions, functions, {"th06::First"})

    assert result["instruction_count"] == 9
    assert result["x87_instruction_count"] == 7
    assert result["unmapped_x87_instruction_count"] == 0
    assert result["xmm_operand_instruction_count"] == 1
    assert result["mapped_xmm_operand_instruction_count"] == 1
    assert result["unmapped_xmm_operand_instruction_count"] == 0
    assert result["xmm_operand_functions"] == [
        {"name": "helper_sin", "instruction_count": 1}
    ]
    assert result["category_counts"] == {
        "control": 1,
        "transcendental": 2,
        "rounding_or_integer_conversion": 1,
        "stores": 2,
    }
    assert result["memory_widths_by_mnemonic"]["fld"] == {"dword": 1}
    first = next(function for function in result["functions"] if function["name"] == "th06::First")
    second = next(function for function in result["functions"] if function["name"] == "th06::Second")
    assert first["implemented"] is True
    assert first["x87_instructions"] == 5
    assert first["store_memory_widths"] == {"dword": 1}
    assert second["implemented"] is False
    assert second["x87_instructions"] == 1
    helper_calls = result["direct_x87_helper_calls_from_th06"]
    assert helper_calls["direct_call_count"] == 1
    assert helper_calls["helper_count"] == 1
    assert helper_calls["helpers"] == [
        {
            "name": "helper_sin",
            "start": "0x00401040",
            "direct_call_count": 1,
            "callers": [
                {
                    "name": "th06::First",
                    "direct_call_count": 1,
                    "sites": ["0x00401012"],
                }
            ],
        }
    ]
    summary = x87_audit.summarize(
        {
            "schema_version": 1,
            "executable": {"sha256": "exe"},
            "mapping": {"sha256": "map", "function_count": 3},
            "implemented": {"sha256": "impl", "function_count": 1},
            "disassembler": "synthetic objdump",
            "audit": result,
        }
    )
    assert summary["mapped_th06_functions"]["function_count"] == 2
    assert summary["mapped_th06_functions"]["marked_implemented_count"] == 1
    assert summary["mapped_th06_functions"]["store_memory_widths"] == {"dword": 2}
    print("validated x87 disassembly parsing and function attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

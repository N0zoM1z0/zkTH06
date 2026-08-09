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
  401016: fcomp  DWORD PTR [esp+0x14]
  40101a: fnstsw ax
  40101c: test   ah,0x5
  40101f: jp     0x401030
  401020: fistp  DWORD PTR [esp]
  401040: fsin
  401042: mov    DWORD PTR [esp],eax
  401044: addss  xmm0,xmm1
"""


def main() -> int:
    instructions = x87_audit.parse_disassembly(DISASSEMBLY)
    assert len(instructions) == 14
    assert sum(x87_audit.is_x87(instruction) for instruction in instructions) == 9
    assert sum(x87_audit.uses_xmm(instruction) for instruction in instructions) == 1

    register_use = x87_audit.parse_disassembly(
        """
  500000: call   0x500100
  500005: mov    eax,0x0
  50000a: push   edx
"""
    )
    register_map = [x87_audit.FunctionRange("th06::RegisterUse", 0x500000, 0x20)]
    assert x87_audit._return_register_observation(
        register_use, 0, x87_audit.FunctionIndex(register_map)
    ) == (False, True)

    partial_use = x87_audit.parse_disassembly(
        """
  500000: call   0x500100
  500005: mov    ecx,DWORD PTR [ebp+0x8]
  500008: mov    BYTE PTR [ecx],al
  50000a: mov    eax,DWORD PTR [ebp-0x4]
  50000d: mov    edx,DWORD PTR [ebp-0x8]
"""
    )
    partial_details = x87_audit._return_register_observation_details(
        partial_use, 0, x87_audit.FunctionIndex(register_map)
    )
    assert partial_details["eax_observed_mask"] == "0x000000ff"
    assert partial_details["edx_observed_mask"] == "0x00000000"
    assert partial_details["eax_live_mask_at_stop"] == "0x00000000"
    assert partial_details["edx_live_mask_at_stop"] == "0x00000000"
    assert partial_details["first_eax_observer"] == {
        "address": "0x00500008",
        "mnemonic": "mov",
        "aliases": ["al"],
    }
    assert partial_details["termination"] == "resolved"

    with tempfile.TemporaryDirectory(prefix="zkth06-x87-") as directory:
        mapping = Path(directory) / "mapping.csv"
        mapping.write_text(
            "th06::First,0x401000,0x20\n"
            "th06::Second,0x401020,0x10\n"
            "helper_sin,0x401040,0x10\n"
        )
        functions = x87_audit.load_mapping(mapping)
        result = x87_audit.audit(instructions, functions, {"th06::First"})

    assert result["instruction_count"] == 14
    assert result["x87_instruction_count"] == 9
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
        "comparisons": 1,
        "stores": 2,
    }
    assert result["memory_widths_by_mnemonic"]["fld"] == {"dword": 1}
    first = next(function for function in result["functions"] if function["name"] == "th06::First")
    second = next(function for function in result["functions"] if function["name"] == "th06::Second")
    assert first["implemented"] is True
    assert first["x87_instructions"] == 7
    assert first["comparison_instructions"] == 1
    assert first["comparison_memory_widths"] == {"dword": 1}
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
            "predecessor_mnemonics": {"fldcw": 1},
            "bounded_eax_observed_count": 0,
            "bounded_edx_observed_count": 0,
            "eax_observed_masks": {"0x00000000": 1},
            "edx_observed_masks": {"0x00000000": 1},
            "callers": [
                {
                    "name": "th06::First",
                    "direct_call_count": 1,
                    "sites": [
                        {
                            "address": "0x00401012",
                            "function_offset": 0x12,
                            "predecessor": {
                                "address": "0x0040100e",
                                "mnemonic": "fldcw",
                            },
                            "result_observation": {
                                "scan_instruction_limit": 32,
                                "eax_observed_mask": "0x00000000",
                                "edx_observed_mask": "0x00000000",
                                "eax_live_mask_at_stop": "0xffff0000",
                                "edx_live_mask_at_stop": "0xffffffff",
                                "first_eax_observer": None,
                                "first_edx_observer": None,
                                "termination": "control-flow-boundary",
                                "termination_address": "0x0040101f",
                            },
                        }
                    ],
                }
            ],
        }
    ]
    summary = x87_audit.summarize(
        {
            "schema_version": x87_audit.SCHEMA_VERSION,
            "executable": {"sha256": "exe"},
            "mapping": {"sha256": "map", "function_count": 3},
            "implemented": {"sha256": "impl", "function_count": 1},
            "disassembler": "synthetic objdump",
            "audit": result,
        }
    )
    assert summary["mapped_th06_functions"]["function_count"] == 2
    assert summary["mapped_th06_functions"]["marked_implemented_count"] == 1
    assert summary["mapped_th06_functions"]["comparison_memory_widths"] == {"dword": 1}
    assert summary["mapped_th06_functions"]["comparison_consumer_chain_count"] == 1
    assert summary["mapped_th06_functions"]["comparison_consumer_signatures"] == {
        "fnstsw ax; test ah,0x5; jp": 1
    }
    assert summary["mapped_th06_functions"]["comparison_sites"] == [
        {
            "address": "0x00401016",
            "mnemonic": "fcomp",
            "operands": "DWORD PTR [esp+0x14]",
            "function": "th06::First",
            "function_offset": 0x16,
            "memory_width": "dword",
            "status_transfer": "fnstsw ax",
            "status_filter": "test ah,0x5",
            "conditional_branch": "jp",
            "consumer_signature": "fnstsw ax; test ah,0x5; jp",
        }
    ]
    assert summary["mapped_th06_functions"]["store_memory_widths"] == {"dword": 2}
    helper_summary = summary["direct_x87_helper_calls_from_th06"]["helpers"][0]
    assert helper_summary["eax_observed_masks"] == {"0x00000000": 1}
    assert helper_summary["sites"][0]["function"] == "th06::First"
    print("validated x87 disassembly parsing and function attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

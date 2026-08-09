#!/usr/bin/env python3
"""Inventory x87 semantics in a verified 32-bit PE and attribute mapped sites."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 1
INSTRUCTION_RE = re.compile(r"^\s*([0-9a-fA-F]+):\s+([A-Za-z][A-Za-z0-9]*)\s*(.*)$")
MEMORY_WIDTH_RE = re.compile(r"\b(BYTE|WORD|DWORD|QWORD|TBYTE) PTR\b")
XMM_REGISTER_RE = re.compile(r"\bxmm(?:[0-9]|1[0-5])\b", re.IGNORECASE)

CONTROL_MNEMONICS = frozenset(
    {
        "fclex",
        "finit",
        "fldcw",
        "fldenv",
        "fnclex",
        "fninit",
        "fnsave",
        "fnstcw",
        "fnstenv",
        "frstor",
        "fsave",
        "fstcw",
        "fstenv",
    }
)
TRANSCENDENTAL_MNEMONICS = frozenset(
    {"f2xm1", "fcos", "fpatan", "fprem", "fprem1", "fptan", "fsin", "fsincos", "fsqrt", "fyl2x"}
)
ROUNDING_MNEMONICS = frozenset({"fist", "fistp", "fisttp", "frndint"})
STORE_MNEMONICS = frozenset({"fist", "fistp", "fisttp", "fst", "fstp"})

# These entry points transfer control into adjacent or shared x87 bodies, so
# their small mapping ranges do not themselves contain the relevant x87
# instructions. They are explicit exceptions to the otherwise mechanical
# "callee contains x87" helper-call rule below.
X87_WRAPPER_NAMES = frozenset({"atan2", "cos", "sin", "sqrt", "tan"})


@dataclass(frozen=True)
class Instruction:
    address: int
    mnemonic: str
    operands: str


@dataclass(frozen=True)
class FunctionRange:
    name: str
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_disassembly(text: str) -> list[Instruction]:
    instructions: list[Instruction] = []
    for line in text.splitlines():
        match = INSTRUCTION_RE.match(line)
        if match is None:
            continue
        address, mnemonic, operands = match.groups()
        instructions.append(Instruction(int(address, 16), mnemonic.lower(), operands.strip()))
    return instructions


def is_x87(instruction: Instruction) -> bool:
    return instruction.mnemonic.startswith("f") and instruction.mnemonic != "fs"


def uses_xmm(instruction: Instruction) -> bool:
    return XMM_REGISTER_RE.search(instruction.operands) is not None


def load_mapping(path: Path) -> list[FunctionRange]:
    functions: list[FunctionRange] = []
    with path.open(newline="") as file:
        for line_number, row in enumerate(csv.reader(file), 1):
            if len(row) < 3:
                raise ValueError(f"{path}:{line_number}: expected at least three CSV columns")
            try:
                start = int(row[1], 0)
                size = int(row[2], 0)
            except ValueError as error:
                raise ValueError(f"{path}:{line_number}: invalid address or size") from error
            if size <= 0:
                raise ValueError(f"{path}:{line_number}: function size must be positive")
            functions.append(FunctionRange(row[0], start, size))
    functions.sort(key=lambda function: function.start)
    return functions


def load_name_set(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


class FunctionIndex:
    def __init__(self, functions: list[FunctionRange]):
        self.functions = functions
        self.starts = [function.start for function in functions]

    def find(self, address: int) -> FunctionRange | None:
        index = bisect.bisect_right(self.starts, address) - 1
        # The upstream mapping contains a few intentional aliases and nested
        # CRT helpers. Prefer the containing range with the greatest start.
        while index >= 0:
            function = self.functions[index]
            if address < function.end:
                return function
            index -= 1
        return None


def memory_width(instruction: Instruction) -> str:
    match = MEMORY_WIDTH_RE.search(instruction.operands.upper())
    return "none" if match is None else match.group(1).lower()


def site_dict(instruction: Instruction, function: FunctionRange | None) -> dict[str, object]:
    return {
        "address": f"0x{instruction.address:08x}",
        "mnemonic": instruction.mnemonic,
        "operands": instruction.operands,
        "function": None if function is None else function.name,
        "function_offset": None if function is None else instruction.address - function.start,
    }


def direct_call_target(instruction: Instruction) -> int | None:
    """Return the absolute target of a direct objdump call, if present."""
    if instruction.mnemonic != "call":
        return None
    try:
        return int(instruction.operands.split(maxsplit=1)[0], 0)
    except (ValueError, IndexError):
        return None


def x87_helper_calls_from_th06(
    instructions: list[Instruction],
    function_index: "FunctionIndex",
    x87_function_names: set[str],
) -> dict[str, object]:
    """Aggregate direct calls from reconstructed game code into x87 helpers."""
    helpers: dict[tuple[str, int], dict[str, object]] = {}
    call_count = 0
    for instruction in instructions:
        target = direct_call_target(instruction)
        if target is None:
            continue
        caller = function_index.find(instruction.address)
        callee = function_index.find(target)
        if (
            caller is None
            or callee is None
            or not caller.name.startswith("th06::")
            or callee.name.startswith("th06::")
            or (callee.name not in x87_function_names and callee.name not in X87_WRAPPER_NAMES)
            or target != callee.start
        ):
            continue

        call_count += 1
        helper = helpers.setdefault(
            (callee.name, callee.start),
            {
                "name": callee.name,
                "start": f"0x{callee.start:08x}",
                "direct_call_count": 0,
                "callers": {},
            },
        )
        helper["direct_call_count"] += 1
        caller_entry = helper["callers"].setdefault(
            caller.name,
            {"name": caller.name, "direct_call_count": 0, "sites": []},
        )
        caller_entry["direct_call_count"] += 1
        caller_entry["sites"].append(f"0x{instruction.address:08x}")

    helper_rows: list[dict[str, object]] = []
    for helper in helpers.values():
        helper["callers"] = sorted(helper["callers"].values(), key=lambda row: row["name"])
        helper_rows.append(helper)
    helper_rows.sort(key=lambda row: (-row["direct_call_count"], row["start"]))
    return {
        "direct_call_count": call_count,
        "helper_count": len(helper_rows),
        "helpers": helper_rows,
    }


def audit(
    instructions: list[Instruction],
    functions: list[FunctionRange],
    implemented: set[str],
) -> dict[str, object]:
    function_index = FunctionIndex(functions)
    x87 = [instruction for instruction in instructions if is_x87(instruction)]
    xmm = [instruction for instruction in instructions if uses_xmm(instruction)]
    mnemonic_counts = Counter(instruction.mnemonic for instruction in x87)
    width_counts: dict[str, Counter[str]] = {}
    for instruction in x87:
        width_counts.setdefault(instruction.mnemonic, Counter())[memory_width(instruction)] += 1

    per_function: dict[str, dict[str, object]] = {}
    unmapped = 0
    key_sites: list[dict[str, object]] = []
    for instruction in x87:
        function = function_index.find(instruction.address)
        if function is None:
            unmapped += 1
        else:
            entry = per_function.setdefault(
                function.name,
                {
                    "name": function.name,
                    "start": f"0x{function.start:08x}",
                    "size": function.size,
                    "implemented": function.name in implemented if implemented else None,
                    "x87_instructions": 0,
                    "mnemonics": Counter(),
                    "memory_widths": Counter(),
                    "control_instructions": 0,
                    "transcendental_instructions": 0,
                    "rounding_instructions": 0,
                    "store_instructions": 0,
                    "store_memory_widths": Counter(),
                },
            )
            entry["x87_instructions"] += 1
            entry["mnemonics"][instruction.mnemonic] += 1
            entry["memory_widths"][memory_width(instruction)] += 1
            entry["control_instructions"] += instruction.mnemonic in CONTROL_MNEMONICS
            entry["transcendental_instructions"] += instruction.mnemonic in TRANSCENDENTAL_MNEMONICS
            entry["rounding_instructions"] += instruction.mnemonic in ROUNDING_MNEMONICS
            entry["store_instructions"] += instruction.mnemonic in STORE_MNEMONICS
            if instruction.mnemonic in STORE_MNEMONICS:
                entry["store_memory_widths"][memory_width(instruction)] += 1
        if (
            instruction.mnemonic in CONTROL_MNEMONICS
            or instruction.mnemonic in TRANSCENDENTAL_MNEMONICS
            or instruction.mnemonic in ROUNDING_MNEMONICS
        ):
            key_sites.append(site_dict(instruction, function))

    function_rows = []
    for entry in per_function.values():
        entry["mnemonics"] = dict(sorted(entry["mnemonics"].items()))
        entry["memory_widths"] = dict(sorted(entry["memory_widths"].items()))
        entry["store_memory_widths"] = dict(sorted(entry["store_memory_widths"].items()))
        function_rows.append(entry)
    function_rows.sort(key=lambda entry: (-entry["x87_instructions"], entry["start"]))

    helper_calls = x87_helper_calls_from_th06(instructions, function_index, set(per_function))
    xmm_functions = Counter()
    unmapped_xmm = 0
    for instruction in xmm:
        function = function_index.find(instruction.address)
        if function is None:
            unmapped_xmm += 1
        else:
            xmm_functions[function.name] += 1

    return {
        "instruction_count": len(instructions),
        "x87_instruction_count": len(x87),
        "mapped_x87_instruction_count": len(x87) - unmapped,
        "unmapped_x87_instruction_count": unmapped,
        "xmm_operand_instruction_count": len(xmm),
        "mapped_xmm_operand_instruction_count": len(xmm) - unmapped_xmm,
        "unmapped_xmm_operand_instruction_count": unmapped_xmm,
        "xmm_operand_functions": [
            {"name": name, "instruction_count": count}
            for name, count in sorted(xmm_functions.items(), key=lambda item: (-item[1], item[0]))
        ],
        "mnemonics": dict(sorted(mnemonic_counts.items())),
        "memory_widths_by_mnemonic": {
            mnemonic: dict(sorted(counts.items())) for mnemonic, counts in sorted(width_counts.items())
        },
        "category_counts": {
            "control": sum(mnemonic_counts[mnemonic] for mnemonic in CONTROL_MNEMONICS),
            "transcendental": sum(mnemonic_counts[mnemonic] for mnemonic in TRANSCENDENTAL_MNEMONICS),
            "rounding_or_integer_conversion": sum(mnemonic_counts[mnemonic] for mnemonic in ROUNDING_MNEMONICS),
            "stores": sum(mnemonic_counts[mnemonic] for mnemonic in STORE_MNEMONICS),
        },
        "key_sites": key_sites,
        "functions": function_rows,
        "direct_x87_helper_calls_from_th06": helper_calls,
    }


def summarize(result: dict[str, object]) -> dict[str, object]:
    """Build a compact, path-free report suitable for tracked evidence."""
    audit_result = result["audit"]
    game_functions = [
        function
        for function in audit_result["functions"]
        if function["name"].startswith("th06::")
    ]
    category_fields = {
        "control": "control_instructions",
        "transcendental": "transcendental_instructions",
        "rounding_or_integer_conversion": "rounding_instructions",
        "stores": "store_instructions",
    }
    game_categories = {
        name: sum(function[field] for function in game_functions)
        for name, field in category_fields.items()
    }
    game_mnemonics = Counter()
    game_store_widths = Counter()
    for function in game_functions:
        game_mnemonics.update(function["mnemonics"])
        game_store_widths.update(function["store_memory_widths"])

    helper_summary = audit_result["direct_x87_helper_calls_from_th06"]
    return {
        "schema_version": result["schema_version"],
        "inputs": {
            "executable_sha256": result["executable"]["sha256"],
            "mapping_sha256": result["mapping"]["sha256"],
            "mapping_function_count": result["mapping"]["function_count"],
            "implemented_sha256": None
            if result["implemented"] is None
            else result["implemented"]["sha256"],
            "implemented_function_count": None
            if result["implemented"] is None
            else result["implemented"]["function_count"],
        },
        "disassembler": result["disassembler"],
        "linear_disassembly": {
            "instruction_count": audit_result["instruction_count"],
            "x87_instruction_count": audit_result["x87_instruction_count"],
            "mapped_x87_instruction_count": audit_result["mapped_x87_instruction_count"],
            "unmapped_x87_instruction_count": audit_result["unmapped_x87_instruction_count"],
            "categories": audit_result["category_counts"],
            "mnemonics": audit_result["mnemonics"],
            "memory_widths_by_mnemonic": audit_result["memory_widths_by_mnemonic"],
            "xmm_operand_instruction_count": audit_result["xmm_operand_instruction_count"],
            "mapped_xmm_operand_instruction_count": audit_result[
                "mapped_xmm_operand_instruction_count"
            ],
            "unmapped_xmm_operand_instruction_count": audit_result[
                "unmapped_xmm_operand_instruction_count"
            ],
            "xmm_operand_functions": audit_result["xmm_operand_functions"],
        },
        "mapped_th06_functions": {
            "function_count": len(game_functions),
            "marked_implemented_count": sum(
                function["implemented"] is True for function in game_functions
            ),
            "x87_instruction_count": sum(
                function["x87_instructions"] for function in game_functions
            ),
            "categories": game_categories,
            "mnemonics": dict(sorted(game_mnemonics.items())),
            "store_memory_widths": dict(sorted(game_store_widths.items())),
            "top_functions": game_functions[:25],
            "transcendental_sites": [
                site
                for site in audit_result["key_sites"]
                if site["mnemonic"] in TRANSCENDENTAL_MNEMONICS
                and site["function"] is not None
                and site["function"].startswith("th06::")
            ],
        },
        "direct_x87_helper_calls_from_th06": {
            "direct_call_count": helper_summary["direct_call_count"],
            "helper_count": helper_summary["helper_count"],
            "helpers": [
                {
                    "name": helper["name"],
                    "start": helper["start"],
                    "direct_call_count": helper["direct_call_count"],
                    "callers": [
                        {
                            "name": caller["name"],
                            "direct_call_count": caller["direct_call_count"],
                        }
                        for caller in helper["callers"]
                    ],
                }
                for helper in helper_summary["helpers"]
            ],
        },
    }


def run_objdump(executable: Path, program: str) -> tuple[str, str]:
    version = subprocess.run(
        [program, "--version"], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.splitlines()[0]
    result = subprocess.run(
        [program, "-d", "-M", "intel", "--no-show-raw-insn", str(executable)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return version, result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="verified 32-bit PE to disassemble")
    parser.add_argument("--mapping", type=Path, required=True, help="authoritative function mapping CSV")
    parser.add_argument("--implemented", type=Path, help="optional newline-delimited implemented-function list")
    parser.add_argument("--objdump", default="objdump", help="GNU objdump-compatible executable")
    parser.add_argument("--summary", action="store_true", help="emit a compact path-free evidence report")
    args = parser.parse_args()

    version, disassembly = run_objdump(args.executable, args.objdump)
    functions = load_mapping(args.mapping)
    implemented = load_name_set(args.implemented)
    result = {
        "schema_version": SCHEMA_VERSION,
        "executable": {
            "path": str(args.executable),
            "sha256": sha256_file(args.executable),
        },
        "mapping": {
            "path": str(args.mapping),
            "sha256": sha256_file(args.mapping),
            "function_count": len(functions),
        },
        "implemented": None
        if args.implemented is None
        else {
            "path": str(args.implemented),
            "sha256": sha256_file(args.implemented),
            "function_count": len(implemented),
        },
        "disassembler": version,
        "audit": audit(parse_disassembly(disassembly), functions, implemented),
    }
    print(json.dumps(summarize(result) if args.summary else result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

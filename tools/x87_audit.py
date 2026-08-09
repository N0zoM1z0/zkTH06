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


SCHEMA_VERSION = 2
INSTRUCTION_RE = re.compile(r"^\s*([0-9a-fA-F]+):\s+([A-Za-z][A-Za-z0-9]*)\s*(.*)$")
MEMORY_WIDTH_RE = re.compile(r"\b(BYTE|WORD|DWORD|QWORD|TBYTE) PTR\b")
XMM_REGISTER_RE = re.compile(r"\bxmm(?:[0-9]|1[0-5])\b", re.IGNORECASE)
EAX_REGISTER_RE = re.compile(r"\b(?:eax|ax|ah|al)\b", re.IGNORECASE)
EDX_REGISTER_RE = re.compile(r"\b(?:edx|dx|dh|dl)\b", re.IGNORECASE)

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
COMPARISON_MNEMONICS = frozenset(
    {
        "fcom",
        "fcomi",
        "fcomip",
        "fcomp",
        "fcompp",
        "ftst",
        "fucom",
        "fucomi",
        "fucomip",
        "fucomp",
        "fucompp",
    }
)

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


def comparison_site_dict(
    instructions: list[Instruction],
    index: int,
    function_index: "FunctionIndex",
) -> dict[str, object]:
    """Describe the bounded status-word consumer after one x87 comparison.

    MSVC 7 normally lowers a source comparison to FCOMP, FNSTSW AX, a TEST or
    AND mask, and a conditional branch.  This recognizer deliberately records
    only that local syntactic fact; it does not claim reachability or recover a
    source-level predicate.
    """
    instruction = instructions[index]
    function = function_index.find(instruction.address)
    site = site_dict(instruction, function)
    site["memory_width"] = memory_width(instruction)
    site["status_transfer"] = None
    site["status_filter"] = None
    site["conditional_branch"] = None
    site["consumer_signature"] = None

    followers: list[Instruction] = []
    for candidate in instructions[index + 1 : index + 5]:
        if function_index.find(candidate.address) != function:
            break
        followers.append(candidate)
    if len(followers) < 3:
        return site

    status, status_filter, branch = followers[:3]
    if status.mnemonic not in {"fnstsw", "fstsw"}:
        return site
    if status_filter.mnemonic not in {"and", "test"}:
        return site
    if not branch.mnemonic.startswith("j") or branch.mnemonic == "jmp":
        return site

    site["status_transfer"] = f"{status.mnemonic} {status.operands}".strip()
    site["status_filter"] = f"{status_filter.mnemonic} {status_filter.operands}".strip()
    site["conditional_branch"] = branch.mnemonic
    site["consumer_signature"] = "; ".join(
        (site["status_transfer"], site["status_filter"], branch.mnemonic)
    )
    return site


def direct_call_target(instruction: Instruction) -> int | None:
    """Return the absolute target of a direct objdump call, if present."""
    if instruction.mnemonic != "call":
        return None
    try:
        return int(instruction.operands.split(maxsplit=1)[0], 0)
    except (ValueError, IndexError):
        return None


def _destination_register(instruction: Instruction) -> str | None:
    destination = instruction.operands.split(",", 1)[0].strip().lower()
    return destination if re.fullmatch(r"e?[abcd]x|[abcd][hl]", destination) else None


def _return_register_observation(
    instructions: list[Instruction],
    call_index: int,
    function_index: "FunctionIndex",
) -> tuple[bool, bool]:
    """Conservatively scan one straight-line suffix for EDX:EAX consumption."""
    function = function_index.find(instructions[call_index].address)
    eax_live = True
    edx_live = True
    eax_observed = False
    edx_observed = False
    write_only = {"lea", "mov", "movsx", "movzx", "pop"}

    for instruction in instructions[call_index + 1 : call_index + 33]:
        if function_index.find(instruction.address) != function:
            break
        destination = _destination_register(instruction)
        reads_eax = EAX_REGISTER_RE.search(instruction.operands) is not None
        reads_edx = EDX_REGISTER_RE.search(instruction.operands) is not None
        if instruction.mnemonic in write_only:
            if destination in {"eax", "ax", "ah", "al"}:
                reads_eax = False
            if destination in {"edx", "dx", "dh", "dl"}:
                reads_edx = False
        if instruction.mnemonic in {"sub", "xor"}:
            operands = [part.strip().lower() for part in instruction.operands.split(",")]
            if len(operands) == 2 and operands[0] == operands[1]:
                reads_eax = reads_eax and operands[0] not in {"eax", "ax", "ah", "al"}
                reads_edx = reads_edx and operands[0] not in {"edx", "dx", "dh", "dl"}

        if eax_live and reads_eax:
            eax_observed = True
            eax_live = False
        if edx_live and reads_edx:
            edx_observed = True
            edx_live = False

        if destination == "eax" or instruction.mnemonic == "call":
            eax_live = False
        if destination == "edx" or instruction.mnemonic == "call":
            edx_live = False
        if instruction.mnemonic.startswith("j") or instruction.mnemonic.startswith("ret"):
            break
        if not eax_live and not edx_live:
            break
    return eax_observed, edx_observed


def x87_helper_calls_from_th06(
    instructions: list[Instruction],
    function_index: "FunctionIndex",
    x87_function_names: set[str],
) -> dict[str, object]:
    """Aggregate direct calls from reconstructed game code into x87 helpers."""
    helpers: dict[tuple[str, int], dict[str, object]] = {}
    call_count = 0
    for instruction_index, instruction in enumerate(instructions):
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
                "predecessor_mnemonics": Counter(),
                "bounded_eax_observed_count": 0,
                "bounded_edx_observed_count": 0,
            },
        )
        helper["direct_call_count"] += 1
        if instruction_index:
            helper["predecessor_mnemonics"][instructions[instruction_index - 1].mnemonic] += 1
        eax_observed, edx_observed = _return_register_observation(
            instructions, instruction_index, function_index
        )
        helper["bounded_eax_observed_count"] += eax_observed
        helper["bounded_edx_observed_count"] += edx_observed
        caller_entry = helper["callers"].setdefault(
            caller.name,
            {"name": caller.name, "direct_call_count": 0, "sites": []},
        )
        caller_entry["direct_call_count"] += 1
        caller_entry["sites"].append(f"0x{instruction.address:08x}")

    helper_rows: list[dict[str, object]] = []
    for helper in helpers.values():
        helper["callers"] = sorted(helper["callers"].values(), key=lambda row: row["name"])
        helper["predecessor_mnemonics"] = dict(sorted(helper["predecessor_mnemonics"].items()))
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
                    "comparison_instructions": 0,
                    "comparison_memory_widths": Counter(),
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
            entry["comparison_instructions"] += instruction.mnemonic in COMPARISON_MNEMONICS
            if instruction.mnemonic in COMPARISON_MNEMONICS:
                entry["comparison_memory_widths"][memory_width(instruction)] += 1
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
        entry["comparison_memory_widths"] = dict(
            sorted(entry["comparison_memory_widths"].items())
        )
        entry["store_memory_widths"] = dict(sorted(entry["store_memory_widths"].items()))
        function_rows.append(entry)
    function_rows.sort(key=lambda entry: (-entry["x87_instructions"], entry["start"]))

    helper_calls = x87_helper_calls_from_th06(instructions, function_index, set(per_function))
    comparison_sites = [
        comparison_site_dict(instructions, index, function_index)
        for index, instruction in enumerate(instructions)
        if instruction.mnemonic in COMPARISON_MNEMONICS
    ]
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
            "comparisons": sum(mnemonic_counts[mnemonic] for mnemonic in COMPARISON_MNEMONICS),
            "stores": sum(mnemonic_counts[mnemonic] for mnemonic in STORE_MNEMONICS),
        },
        "key_sites": key_sites,
        "comparison_sites": comparison_sites,
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
        "comparisons": "comparison_instructions",
        "stores": "store_instructions",
    }
    game_categories = {
        name: sum(function[field] for function in game_functions)
        for name, field in category_fields.items()
    }
    game_mnemonics = Counter()
    game_store_widths = Counter()
    game_comparison_widths = Counter()
    for function in game_functions:
        game_mnemonics.update(function["mnemonics"])
        game_store_widths.update(function["store_memory_widths"])
        game_comparison_widths.update(function["comparison_memory_widths"])

    game_comparison_sites = [
        site
        for site in audit_result["comparison_sites"]
        if site["function"] is not None and site["function"].startswith("th06::")
    ]
    comparison_consumer_signatures = Counter(
        site["consumer_signature"]
        for site in game_comparison_sites
        if site["consumer_signature"] is not None
    )

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
            "comparison_memory_widths": dict(sorted(game_comparison_widths.items())),
            "comparison_consumer_chain_count": sum(comparison_consumer_signatures.values()),
            "comparison_consumer_signatures": dict(
                sorted(comparison_consumer_signatures.items())
            ),
            "store_memory_widths": dict(sorted(game_store_widths.items())),
            "top_functions": game_functions[:25],
            "transcendental_sites": [
                site
                for site in audit_result["key_sites"]
                if site["mnemonic"] in TRANSCENDENTAL_MNEMONICS
                and site["function"] is not None
                and site["function"].startswith("th06::")
            ],
            "comparison_sites": game_comparison_sites,
        },
        "direct_x87_helper_calls_from_th06": {
            "direct_call_count": helper_summary["direct_call_count"],
            "helper_count": helper_summary["helper_count"],
            "helpers": [
                {
                    "name": helper["name"],
                    "start": helper["start"],
                    "direct_call_count": helper["direct_call_count"],
                    "predecessor_mnemonics": helper["predecessor_mnemonics"],
                    "bounded_eax_observed_count": helper["bounded_eax_observed_count"],
                    "bounded_edx_observed_count": helper["bounded_edx_observed_count"],
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

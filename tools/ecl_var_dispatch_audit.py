#!/usr/bin/env python3
"""Audit the pinned binary's narrow GetVarFloat/__ftol2 observation contract."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import run_ftol2_probe
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.ecl-var-dispatch-audit"
GET_VAR_ADDRESS = 0x0040AFB0
GET_VAR_SIZE = 0x36C
GET_VAR_FLOAT_ADDRESS = 0x0040B380
GET_VAR_FLOAT_SIZE = 0x40
JUMP_TABLE_ADDRESS = 0x0040B31C
JUMP_TABLE_COUNT = 25
NORMALIZATION_ADDEND = 0x2729
MAX_INDEX = 0x18
FIRST_VAR_ID = -10025
LAST_VAR_ID = -10001

EXPECTED_INSTRUCTIONS = {
    0x0040AFC8: ("mov", "edx,DWORD PTR [ecx]", "load candidate integer"),
    0x0040AFD0: ("add", "eax,0x2729", "normalize -10025 to table index zero"),
    0x0040AFD8: ("cmp", "DWORD PTR [ebp-0x24],0x18", "compare index with 24"),
    0x0040AFDC: ("ja", "0x40b315", "unsigned out-of-range branch"),
    0x0040AFE5: ("jmp", "DWORD PTR [ecx*4+0x40b31c]", "dispatch through 25-entry table"),
    0x0040B315: ("mov", "eax,DWORD PTR [ebp+0xc]", "default returns input integer pointer"),
    0x0040B389: ("fld", "DWORD PTR [eax]", "load float operand"),
    0x0040B38B: ("call", "0x45ba78", "call pinned __ftol2"),
    0x0040B390: ("mov", "DWORD PTR [ebp-0x8],eax", "store low conversion result"),
    0x0040B397: ("lea", "edx,[ebp-0x8]", "take local integer address"),
    0x0040B39F: ("call", "0x40afb0", "resolve integer through GetVar"),
    0x0040B3A7: ("mov", "DWORD PTR [ebp-0x4],eax", "store resolved pointer"),
    0x0040B3AD: ("lea", "edx,[ebp-0x8]", "recover local integer address"),
    0x0040B3B0: ("cmp", "ecx,edx", "test whether GetVar took default"),
    0x0040B3B2: ("jne", "0x40b3b9", "return resolved variable pointer"),
    0x0040B3B4: ("mov", "eax,DWORD PTR [ebp+0xc]", "default returns original float pointer"),
    0x0040B3B9: ("mov", "eax,DWORD PTR [ebp-0x4]", "select resolved pointer"),
}


def instruction_index(disassembly: str) -> dict[int, x87_audit.Instruction]:
    return {instruction.address: instruction for instruction in x87_audit.parse_disassembly(disassembly)}


def verify_instruction_contract(
    instructions: dict[int, x87_audit.Instruction],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for address, (mnemonic, operands, role) in EXPECTED_INSTRUCTIONS.items():
        instruction = instructions.get(address)
        if instruction is None:
            raise ValueError(f"missing instruction at 0x{address:08x}")
        if (instruction.mnemonic, instruction.operands) != (mnemonic, operands):
            raise ValueError(
                f"instruction mismatch at 0x{address:08x}: got "
                f"{instruction.mnemonic} {instruction.operands!r}, expected "
                f"{mnemonic} {operands!r}"
            )
        rows.append(
            {"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role}
        )
    return rows


def verify_function_mapping(mapping: list[x87_audit.FunctionRange]) -> list[dict[str, Any]]:
    expected = {
        "th06::EnemyEclInstr::GetVar": (GET_VAR_ADDRESS, GET_VAR_SIZE),
        "th06::EnemyEclInstr::GetVarFloat": (GET_VAR_FLOAT_ADDRESS, GET_VAR_FLOAT_SIZE),
    }
    by_name = {function.name: function for function in mapping}
    rows: list[dict[str, Any]] = []
    for name, (start, size) in expected.items():
        function = by_name.get(name)
        if function is None or (function.start, function.size) != (start, size):
            actual = None if function is None else (function.start, function.size)
            raise ValueError(f"mapping mismatch for {name}: expected {(start, size)}, got {actual}")
        rows.append({"name": name, "start": f"0x{start:08x}", "size": size})
    return rows


def build_document(
    executable: Path,
    mapping_path: Path,
    objdump: str,
    base_ledger: dict[str, Any],
    tool_path: Path,
) -> dict[str, Any]:
    image = executable.read_bytes()
    executable_hash = run_ftol2_probe.sha256(image)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable hash does not match the pinned Japanese v1.02h image")
    mapping_hash = x87_audit.sha256_file(mapping_path)
    if mapping_hash != arithmetic_obligations.PINNED_MAPPING_SHA256:
        raise ValueError("mapping hash does not match the pinned authoritative mapping")
    if (
        arithmetic_obligations.document_digest(base_ledger)
        != base_ledger.get("artifact_sha256")
    ):
        raise ValueError("base arithmetic ledger has an invalid digest")

    mapping = x87_audit.load_mapping(mapping_path)
    functions = verify_function_mapping(mapping)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instruction_contract(instruction_index(disassembly))
    table_bytes = run_ftol2_probe.extract_pe_range(
        image, JUMP_TABLE_ADDRESS, JUMP_TABLE_COUNT * 4
    )
    targets = [target for (target,) in struct.iter_unpack("<I", table_bytes)]
    if len(set(targets)) != JUMP_TABLE_COUNT:
        raise ValueError("GetVar jump table does not have 25 unique targets")
    if not all(GET_VAR_ADDRESS <= target < GET_VAR_ADDRESS + GET_VAR_SIZE for target in targets):
        raise ValueError("GetVar jump target is outside the mapped function")
    table = [
        {
            "normalized_index": index,
            "variable_id": FIRST_VAR_ID + index,
            "target": f"0x{target:08x}",
        }
        for index, target in enumerate(targets)
    ]
    if table[-1]["variable_id"] != LAST_VAR_ID:
        raise ValueError("derived ECL variable interval is inconsistent")

    ftol2_sites = {
        site["call_address"]: site for site in base_ledger["sites"]["ftol2_calls"]
    }
    critical_call = ftol2_sites.get("0x0040b38b")
    if critical_call is None or critical_call["function"] != "th06::EnemyEclInstr::GetVarFloat":
        raise ValueError("base ledger does not contain the expected GetVarFloat helper call")

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
        },
        "generator": {
            "path": "tools/ecl_var_dispatch_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
            "x87_audit_sha256": arithmetic_obligations.sha256_file(
                tool_path.parent / "x87_audit.py"
            ),
            "disassembler": disassembler,
        },
        "mapped_functions": functions,
        "critical_ftol2_obligation_id": critical_call["id"],
        "dispatch_contract": {
            "normalization_addend": NORMALIZATION_ADDEND,
            "maximum_unsigned_index": MAX_INDEX,
            "first_variable_id": FIRST_VAR_ID,
            "last_variable_id": LAST_VAR_ID,
            "jump_table_address": f"0x{JUMP_TABLE_ADDRESS:08x}",
            "jump_table": table,
            "default_behavior": (
                "GetVar returns its input integer pointer; GetVarFloat detects that identity "
                "and returns the original float pointer."
            ),
            "observable_conversion_result": (
                "which, if any, of the 25 contiguous variable IDs is selected"
            ),
        },
        "checked_instruction_roles": instruction_rows,
        "model_contracts": {
            "classifier": "ZkTH06.EclVarId.isVariableId",
            "decoder": "ZkTH06.EclVarId.decodeVariableId",
            "machine_classifier": "ZkTH06.EclVarId.machineIsVariableId",
            "machine_interval_theorem": (
                "ZkTH06.EclVarId.machine_classifier_matches_signed_interval"
            ),
            "default_irrelevance_theorem": (
                "ZkTH06.EclVarId.nonvariable_integer_value_is_irrelevant"
            ),
        },
        "evidence_status": (
            "static decode and derived jump-table facts; not a decoder proof, reachability "
            "proof, helper/classifier refinement, or guest binding"
        ),
        "open_obligations": [
            "Prove or translation-validate the checked instruction sequence and jump-table decode.",
            "Prove exact __ftol2-to-classifier agreement for every reachable raw operand.",
            "Bind the 25 table targets to the modeled variable identities and value types.",
            "Prove the guest ECL resolver refines the address-bound dispatch contract.",
        ],
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument(
        "--ledger", type=Path, default=Path("arithmetic/obligations-v1.json")
    )
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    base_ledger = json.loads(args.ledger.read_text())
    document = build_document(
        args.executable,
        args.mapping,
        args.objdump,
        base_ledger,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale ECL variable dispatch audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current ECL variable dispatch audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

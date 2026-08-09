#!/usr/bin/env python3
"""Audit the pinned __ftol2 body and its masked-invalid low-EAX path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import run_ftol2_probe
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.ftol2-helper-audit"
INTEGER_INDEFINITE = 0x8000000000000000

EXPECTED_INSTRUCTIONS = {
    0x0045BA78: ("push", "ebp", "establish frame"),
    0x0045BA79: ("mov", "ebp,esp", "copy stack pointer"),
    0x0045BA7B: ("sub", "esp,0x20", "reserve local storage"),
    0x0045BA7E: ("and", "esp,0xfffffff0", "align local storage"),
    0x0045BA81: ("fld", "st(0)", "duplicate input"),
    0x0045BA83: ("fst", "DWORD PTR [esp+0x18]", "store binary32 sign probe"),
    0x0045BA87: ("fistp", "QWORD PTR [esp+0x10]", "convert nearest-even or integer-indefinite"),
    0x0045BA8B: ("fild", "QWORD PTR [esp+0x10]", "reload converted integer"),
    0x0045BA8F: ("mov", "edx,DWORD PTR [esp+0x18]", "load input sign probe"),
    0x0045BA93: ("mov", "eax,DWORD PTR [esp+0x10]", "load low result half"),
    0x0045BA97: ("test", "eax,eax", "test low result half"),
    0x0045BA99: ("je", "0x45bad7", "handle zero-low-half result"),
    0x0045BA9B: ("fsubp", "st(1),st", "form rounding residual"),
    0x0045BA9D: ("test", "edx,edx", "test original sign"),
    0x0045BA9F: ("jns", "0x45babf", "select nonnegative correction"),
    0x0045BAA1: ("fstp", "DWORD PTR [esp]", "store negative residual"),
    0x0045BAA4: ("mov", "ecx,DWORD PTR [esp]", "load negative residual bits"),
    0x0045BAA7: ("xor", "ecx,0x80000000", "remove negative residual sign"),
    0x0045BAAD: ("add", "ecx,0x7fffffff", "derive negative correction carry"),
    0x0045BAB3: ("adc", "eax,0x0", "correct negative low result half"),
    0x0045BAB6: ("mov", "edx,DWORD PTR [esp+0x14]", "load high result half"),
    0x0045BABA: ("adc", "edx,0x0", "correct negative high result half"),
    0x0045BABD: ("jmp", "0x45baeb", "join return path"),
    0x0045BABF: ("fstp", "DWORD PTR [esp]", "store nonnegative residual"),
    0x0045BAC2: ("mov", "ecx,DWORD PTR [esp]", "load nonnegative residual bits"),
    0x0045BAC5: ("add", "ecx,0x7fffffff", "derive nonnegative correction borrow"),
    0x0045BACB: ("sbb", "eax,0x0", "correct nonnegative low result half"),
    0x0045BACE: ("mov", "edx,DWORD PTR [esp+0x14]", "load high result half"),
    0x0045BAD2: ("sbb", "edx,0x0", "correct nonnegative high result half"),
    0x0045BAD5: ("jmp", "0x45baeb", "join return path"),
    0x0045BAD7: ("mov", "edx,DWORD PTR [esp+0x14]", "load high result half on zero-low path"),
    0x0045BADB: ("test", "edx,0x7fffffff", "recognize zero or integer-indefinite high half"),
    0x0045BAE1: ("jne", "0x45ba9b", "correct other zero-low-half results"),
    0x0045BAE3: ("fstp", "DWORD PTR [esp+0x18]", "pop reloaded integer on special path"),
    0x0045BAE7: ("fstp", "DWORD PTR [esp+0x18]", "pop original input on special path"),
    0x0045BAEB: ("leave", "", "restore caller stack frame"),
    0x0045BAEC: ("ret", "", "return EDX:EAX"),
}


def load_sealed(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"base ledger has an invalid artifact digest: {path}")
    return document


def verify_base_ledger(base_ledger: dict[str, Any]) -> None:
    if base_ledger.get("target", {}).get("executable_sha256") != run_ftol2_probe.EXECUTABLE_SHA256:
        raise ValueError("base ledger is bound to a different executable")
    classes = {
        row["id"]: row for row in base_ledger.get("obligation_classes", [])
    }
    ftol2 = classes.get("x87-ftol2-low-result-v1")
    if ftol2 is None:
        raise ValueError("base ledger has no __ftol2 obligation class")
    helper_rows = [
        evidence
        for evidence in ftol2.get("evidence", [])
        if evidence.get("helper_address") == f"0x{run_ftol2_probe.HELPER_VIRTUAL_ADDRESS:08x}"
    ]
    if len(helper_rows) != 1:
        raise ValueError("base ledger has no unique pinned helper evidence row")
    row = helper_rows[0]
    if row.get("helper_size") != run_ftol2_probe.HELPER_SIZE:
        raise ValueError("base ledger helper size mismatch")
    if row.get("helper_sha256") != run_ftol2_probe.HELPER_SHA256:
        raise ValueError("base ledger helper digest mismatch")


def verify_instruction_contract(disassembly: str) -> list[dict[str, str]]:
    instructions = {
        instruction.address: instruction
        for instruction in x87_audit.parse_disassembly(disassembly)
    }
    rows: list[dict[str, str]] = []
    for address, (mnemonic, operands, role) in EXPECTED_INSTRUCTIONS.items():
        instruction = instructions.get(address)
        if instruction is None:
            raise ValueError(f"missing helper instruction at 0x{address:08x}")
        if (instruction.mnemonic, instruction.operands) != (mnemonic, operands):
            raise ValueError(
                f"helper mismatch at 0x{address:08x}: got "
                f"{instruction.mnemonic} {instruction.operands!r}, expected "
                f"{mnemonic} {operands!r}"
            )
        rows.append({"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role})
    return rows


def build_document(
    executable: Path,
    base_ledger: dict[str, Any],
    objdump: str,
    tool_path: Path,
) -> dict[str, Any]:
    image = executable.read_bytes()
    executable_hash = run_ftol2_probe.sha256(image)
    if executable_hash != run_ftol2_probe.EXECUTABLE_SHA256:
        raise ValueError("executable hash does not match the pinned Japanese v1.02h image")
    verify_base_ledger(base_ledger)
    helper = run_ftol2_probe.extract_pe_range(
        image,
        run_ftol2_probe.HELPER_VIRTUAL_ADDRESS,
        run_ftol2_probe.HELPER_SIZE,
    )
    if run_ftol2_probe.sha256(helper) != run_ftol2_probe.HELPER_SHA256:
        raise ValueError("extracted helper digest mismatch")
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instructions = verify_instruction_contract(disassembly)

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
        },
        "generator": {
            "path": "tools/ftol2_helper_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
            "x87_audit_sha256": arithmetic_obligations.sha256_file(
                tool_path.parent / "x87_audit.py"
            ),
            "run_ftol2_probe_sha256": arithmetic_obligations.sha256_file(
                tool_path.parent / "run_ftol2_probe.py"
            ),
            "disassembler": disassembler,
        },
        "helper": {
            "address": f"0x{run_ftol2_probe.HELPER_VIRTUAL_ADDRESS:08x}",
            "size": run_ftol2_probe.HELPER_SIZE,
            "sha256": run_ftol2_probe.HELPER_SHA256,
            "entry": "one x87 value in ST(0)",
            "result": "signed 64-bit value split across EDX:EAX",
            "required_control_word": f"0x{run_ftol2_probe.TARGET_CONTROL_WORD:04x}",
        },
        "masked_invalid_path": {
            "architectural_premise": (
                "masked-invalid FISTP m64int stores integer-indefinite "
                "0x8000000000000000"
            ),
            "stored_result": f"0x{INTEGER_INDEFINITE:016x}",
            "eax": "0x00000000",
            "edx": "0x80000000",
            "path": [
                "zero EAX takes the zero-low-half branch",
                "EDX masked by 0x7fffffff is zero",
                "the correction block is skipped",
                "two x87 values are popped before returning unchanged EDX:EAX",
            ],
            "score_site_observation": (
                "the eight point-item callers observe signed EAX, so modeled invalid "
                "conversion supplies zero and selects the top-score branch"
            ),
        },
        "checked_instruction_roles": instructions,
        "model_contracts": {
            "integer_indefinite": "ZkTH06.X87Ftol2.integerIndefinite",
            "register_projection": (
                "ZkTH06.X87Ftol2.integer_indefinite_register_projection"
            ),
            "observed_zero": (
                "ZkTH06.X87Ftol2.integer_indefinite_observed_low32_zero"
            ),
            "total_item_score": (
                "ZkTH06.ItemPointScore.collected_score_range_without_item_finiteness"
            ),
        },
        "evidence_status": (
            "exact static instruction signatures and a proved model consequence; not a "
            "verified decoder, architectural FISTP proof, reachable control-word/stack "
            "invariant, caller binding, or guest refinement"
        ),
        "open_obligations": [
            "Prove or translation-validate the 37 checked helper instructions.",
            "Bind the entry x87 stack, tags, and 0x027f control word at every retained call.",
            "Formalize masked-invalid FISTP m64int and its integer-indefinite store.",
            "Bind the helper branches and stack cleanup to the modeled invalid path.",
            "Bind each point-item FLD m32fp input and collision comparison to the total coordinate model.",
            "Prove the guest conversion and score update refine the address-bound contract.",
        ],
        "counts": {
            "checked_instruction_roles": len(instructions),
            "point_item_callers_using_eax": 8,
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument(
        "--ledger", type=Path, default=Path("arithmetic/obligations-v1.json")
    )
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    document = build_document(
        args.executable,
        load_sealed(args.ledger),
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale __ftol2 helper audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current __ftol2 helper audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

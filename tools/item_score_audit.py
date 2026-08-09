#!/usr/bin/env python3
"""Audit the pinned binary's four point-item score conversion blocks."""

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
KIND = "zkth06.item-score-audit"
FUNCTION_NAME = "th06::ItemManager::OnUpdate"
FUNCTION_ADDRESS = 0x0041F4A0
FUNCTION_SIZE = 0xC58
DIFFICULTY_TABLE_ADDRESS = 0x00420114
ITEM_Y_OFFSET = 0x114
THRESHOLD = 128

PROFILES = [
    {
        "name": "easy-normal",
        "difficulty_values": [0, 1],
        "difficulty_names": ["easy", "normal"],
        "entry_address": 0x0041FB0B,
        "helper_calls": [0x0041FB14, 0x0041FB35],
        "top_score": 100000,
        "bottom_score": 60000,
        "position_multiplier": 100,
    },
    {
        "name": "hard",
        "difficulty_values": [2],
        "difficulty_names": ["hard"],
        "entry_address": 0x0041FB88,
        "helper_calls": [0x0041FB91, 0x0041FBB2],
        "top_score": 150000,
        "bottom_score": 100000,
        "position_multiplier": 180,
    },
    {
        "name": "lunatic",
        "difficulty_values": [3],
        "difficulty_names": ["lunatic"],
        "entry_address": 0x0041FC08,
        "helper_calls": [0x0041FC11, 0x0041FC32],
        "top_score": 200000,
        "bottom_score": 150000,
        "position_multiplier": 270,
    },
    {
        "name": "extra",
        "difficulty_values": [4],
        "difficulty_names": ["extra"],
        "entry_address": 0x0041FC85,
        "helper_calls": [0x0041FC8E, 0x0041FCAF],
        "top_score": 300000,
        "bottom_score": 200000,
        "position_multiplier": 400,
    },
]

EXPECTED_INSTRUCTIONS = {
    0x0041FAE6: ("mov", "eax,ds:0x69bcb0", "load difficulty"),
    0x0041FAEB: ("mov", "DWORD PTR [ebp-0xd8],eax", "store difficulty index"),
    0x0041FAF1: ("cmp", "DWORD PTR [ebp-0xd8],0x4", "bound difficulty by Extra"),
    0x0041FAF8: ("ja", "0x41fd00", "skip score block for an invalid difficulty"),
    0x0041FAFE: ("mov", "ecx,DWORD PTR [ebp-0xd8]", "reload difficulty index"),
    0x0041FB04: ("jmp", "DWORD PTR [ecx*4+0x420114]", "dispatch through difficulty table"),
    # Easy and Normal share one profile.
    0x0041FB0B: ("mov", "edx,DWORD PTR [ebp-0x14]", "load current Item pointer"),
    0x0041FB0E: ("fld", "DWORD PTR [edx+0x114]", "load binary32 Item currentPosition.y"),
    0x0041FB14: ("call", "0x45ba78", "first __ftol2 conversion"),
    0x0041FB19: ("cmp", "eax,0x80", "compare signed converted y with 128"),
    0x0041FB1E: ("jge", "0x41fb2c", "take position-dependent branch"),
    0x0041FB20: ("mov", "DWORD PTR [ebp-0xdc],0x186a0", "select top score 100000"),
    0x0041FB2A: ("jmp", "0x41fb4f", "join easy-normal score"),
    0x0041FB2C: ("mov", "eax,DWORD PTR [ebp-0x14]", "reload current Item pointer"),
    0x0041FB2F: ("fld", "DWORD PTR [eax+0x114]", "reload the same binary32 y"),
    0x0041FB35: ("call", "0x45ba78", "second __ftol2 conversion"),
    0x0041FB3A: ("sub", "eax,0x80", "subtract y threshold"),
    0x0041FB3F: ("imul", "eax,eax,0x64", "multiply position delta by 100"),
    0x0041FB42: ("mov", "ecx,0xea60", "load bottom score 60000"),
    0x0041FB47: ("sub", "ecx,eax", "subtract position penalty"),
    0x0041FB49: ("mov", "DWORD PTR [ebp-0xdc],ecx", "store easy-normal score"),
    0x0041FB4F: ("mov", "edx,DWORD PTR [ebp-0xdc]", "join easy-normal result"),
    0x0041FB55: ("mov", "DWORD PTR [ebp-0x8],edx", "publish easy-normal itemScore"),
    # Hard.
    0x0041FB88: ("mov", "eax,DWORD PTR [ebp-0x14]", "load current Item pointer"),
    0x0041FB8B: ("fld", "DWORD PTR [eax+0x114]", "load binary32 Item currentPosition.y"),
    0x0041FB91: ("call", "0x45ba78", "first __ftol2 conversion"),
    0x0041FB96: ("cmp", "eax,0x80", "compare signed converted y with 128"),
    0x0041FB9B: ("jge", "0x41fba9", "take position-dependent branch"),
    0x0041FB9D: ("mov", "DWORD PTR [ebp-0xe0],0x249f0", "select top score 150000"),
    0x0041FBA7: ("jmp", "0x41fbcf", "join hard score"),
    0x0041FBA9: ("mov", "ecx,DWORD PTR [ebp-0x14]", "reload current Item pointer"),
    0x0041FBAC: ("fld", "DWORD PTR [ecx+0x114]", "reload the same binary32 y"),
    0x0041FBB2: ("call", "0x45ba78", "second __ftol2 conversion"),
    0x0041FBB7: ("sub", "eax,0x80", "subtract y threshold"),
    0x0041FBBC: ("imul", "eax,eax,0xb4", "multiply position delta by 180"),
    0x0041FBC2: ("mov", "edx,0x186a0", "load bottom score 100000"),
    0x0041FBC7: ("sub", "edx,eax", "subtract position penalty"),
    0x0041FBC9: ("mov", "DWORD PTR [ebp-0xe0],edx", "store hard score"),
    0x0041FBCF: ("mov", "eax,DWORD PTR [ebp-0xe0]", "join hard result"),
    0x0041FBD5: ("mov", "DWORD PTR [ebp-0x8],eax", "publish hard itemScore"),
    # Lunatic.
    0x0041FC08: ("mov", "ecx,DWORD PTR [ebp-0x14]", "load current Item pointer"),
    0x0041FC0B: ("fld", "DWORD PTR [ecx+0x114]", "load binary32 Item currentPosition.y"),
    0x0041FC11: ("call", "0x45ba78", "first __ftol2 conversion"),
    0x0041FC16: ("cmp", "eax,0x80", "compare signed converted y with 128"),
    0x0041FC1B: ("jge", "0x41fc29", "take position-dependent branch"),
    0x0041FC1D: ("mov", "DWORD PTR [ebp-0xe4],0x30d40", "select top score 200000"),
    0x0041FC27: ("jmp", "0x41fc4f", "join lunatic score"),
    0x0041FC29: ("mov", "edx,DWORD PTR [ebp-0x14]", "reload current Item pointer"),
    0x0041FC2C: ("fld", "DWORD PTR [edx+0x114]", "reload the same binary32 y"),
    0x0041FC32: ("call", "0x45ba78", "second __ftol2 conversion"),
    0x0041FC37: ("sub", "eax,0x80", "subtract y threshold"),
    0x0041FC3C: ("imul", "eax,eax,0x10e", "multiply position delta by 270"),
    0x0041FC42: ("mov", "ecx,0x249f0", "load bottom score 150000"),
    0x0041FC47: ("sub", "ecx,eax", "subtract position penalty"),
    0x0041FC49: ("mov", "DWORD PTR [ebp-0xe4],ecx", "store lunatic score"),
    0x0041FC4F: ("mov", "edx,DWORD PTR [ebp-0xe4]", "join lunatic result"),
    0x0041FC55: ("mov", "DWORD PTR [ebp-0x8],edx", "publish lunatic itemScore"),
    # Extra.
    0x0041FC85: ("mov", "eax,DWORD PTR [ebp-0x14]", "load current Item pointer"),
    0x0041FC88: ("fld", "DWORD PTR [eax+0x114]", "load binary32 Item currentPosition.y"),
    0x0041FC8E: ("call", "0x45ba78", "first __ftol2 conversion"),
    0x0041FC93: ("cmp", "eax,0x80", "compare signed converted y with 128"),
    0x0041FC98: ("jge", "0x41fca6", "take position-dependent branch"),
    0x0041FC9A: ("mov", "DWORD PTR [ebp-0xe8],0x493e0", "select top score 300000"),
    0x0041FCA4: ("jmp", "0x41fccc", "join extra score"),
    0x0041FCA6: ("mov", "ecx,DWORD PTR [ebp-0x14]", "reload current Item pointer"),
    0x0041FCA9: ("fld", "DWORD PTR [ecx+0x114]", "reload the same binary32 y"),
    0x0041FCAF: ("call", "0x45ba78", "second __ftol2 conversion"),
    0x0041FCB4: ("sub", "eax,0x80", "subtract y threshold"),
    0x0041FCB9: ("imul", "eax,eax,0x190", "multiply position delta by 400"),
    0x0041FCBF: ("mov", "edx,0x30d40", "load bottom score 200000"),
    0x0041FCC4: ("sub", "edx,eax", "subtract position penalty"),
    0x0041FCC6: ("mov", "DWORD PTR [ebp-0xe8],edx", "store extra score"),
    0x0041FCCC: ("mov", "eax,DWORD PTR [ebp-0xe8]", "join extra result"),
    0x0041FCD2: ("mov", "DWORD PTR [ebp-0x8],eax", "publish extra itemScore"),
    # Gameplay-visible score accumulation after all four joins.
    0x0041FD00: ("mov", "ecx,DWORD PTR ds:0x69bca4", "load gameplay score"),
    0x0041FD06: ("add", "ecx,DWORD PTR [ebp-0x8]", "add itemScore with 32-bit wrapping semantics"),
    0x0041FD09: ("mov", "DWORD PTR ds:0x69bca4,ecx", "store gameplay score"),
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
        rows.append({"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role})
    return rows


def verify_function_mapping(mapping: list[x87_audit.FunctionRange]) -> dict[str, Any]:
    matches = [function for function in mapping if function.name == FUNCTION_NAME]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one mapping for {FUNCTION_NAME}")
    function = matches[0]
    if (function.start, function.size) != (FUNCTION_ADDRESS, FUNCTION_SIZE):
        raise ValueError(
            f"mapping mismatch for {FUNCTION_NAME}: "
            f"expected {(FUNCTION_ADDRESS, FUNCTION_SIZE)}, got {(function.start, function.size)}"
        )
    return {
        "name": function.name,
        "start": f"0x{function.start:08x}",
        "size": function.size,
    }


def load_sealed(path: Path, description: str) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"{description} has an invalid artifact digest")
    return document


def build_document(
    executable: Path,
    mapping_path: Path,
    base_ledger: dict[str, Any],
    source_ledger: dict[str, Any],
    helper_audit: dict[str, Any],
    player_audit: dict[str, Any],
    objdump: str,
    tool_path: Path,
) -> dict[str, Any]:
    image = executable.read_bytes()
    executable_hash = run_ftol2_probe.sha256(image)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable hash does not match the pinned Japanese v1.02h image")
    mapping_hash = x87_audit.sha256_file(mapping_path)
    if mapping_hash != arithmetic_obligations.PINNED_MAPPING_SHA256:
        raise ValueError("mapping hash does not match the pinned authoritative mapping")
    if base_ledger.get("target", {}).get("executable_sha256") != executable_hash:
        raise ValueError("base ledger is bound to a different executable")
    if base_ledger.get("target", {}).get("mapping_sha256") != mapping_hash:
        raise ValueError("base ledger is bound to a different mapping")
    if source_ledger.get("base_ledger_artifact_sha256") != base_ledger["artifact_sha256"]:
        raise ValueError("source-candidate ledger is not derived from the selected base ledger")
    if helper_audit.get("kind") != "zkth06.ftol2-helper-audit":
        raise ValueError("selected helper artifact has the wrong kind")
    if helper_audit.get("inputs", {}).get("base_ledger_artifact_sha256") != base_ledger["artifact_sha256"]:
        raise ValueError("helper audit is not derived from the selected base ledger")
    if helper_audit.get("helper", {}).get("sha256") != run_ftol2_probe.HELPER_SHA256:
        raise ValueError("helper audit is bound to a different __ftol2 body")
    if helper_audit.get("masked_invalid_path", {}).get("eax") != "0x00000000":
        raise ValueError("helper audit does not expose the required invalid low-EAX quotient")
    if player_audit.get("kind") != "zkth06.player-position-audit":
        raise ValueError("selected player-position artifact has the wrong kind")
    player_inputs = player_audit.get("inputs", {})
    if (
        player_inputs.get("executable_sha256"),
        player_inputs.get("mapping_sha256"),
        player_inputs.get("base_ledger_artifact_sha256"),
    ) != (executable_hash, mapping_hash, base_ledger["artifact_sha256"]):
        raise ValueError("player-position audit is not derived from the selected target")
    player_contract = player_audit.get("derived_contract", {})
    if (
        player_contract.get("movement_lower_y"),
        player_contract.get("movement_upper_y"),
        player_contract.get("grab_radius_y"),
    ) != ("16", "432", "12"):
        raise ValueError("player-position audit does not expose the required score geometry")

    function = verify_function_mapping(x87_audit.load_mapping(mapping_path))
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instruction_contract(instruction_index(disassembly))

    table_bytes = run_ftol2_probe.extract_pe_range(image, DIFFICULTY_TABLE_ADDRESS, 5 * 4)
    difficulty_targets = [target for (target,) in struct.iter_unpack("<I", table_bytes)]
    expected_targets = [
        PROFILES[0]["entry_address"],
        PROFILES[0]["entry_address"],
        PROFILES[1]["entry_address"],
        PROFILES[2]["entry_address"],
        PROFILES[3]["entry_address"],
    ]
    if difficulty_targets != expected_targets:
        raise ValueError(
            f"difficulty dispatch mismatch: expected {expected_targets}, got {difficulty_targets}"
        )

    base_by_address = {
        int(site["call_address"], 16): site for site in base_ledger["sites"]["ftol2_calls"]
    }
    source_by_address = {
        int(site["call_address"], 16): site for site in source_ledger["sites"]
    }
    profiles: list[dict[str, Any]] = []
    for profile in PROFILES:
        calls = profile["helper_calls"]
        if any(call not in base_by_address or call not in source_by_address for call in calls):
            raise ValueError(f"missing helper obligation for {profile['name']}")
        if any(base_by_address[call]["function"] != FUNCTION_NAME for call in calls):
            raise ValueError(f"base-ledger function mismatch for {profile['name']}")
        if any(
            source_by_address[call]["semantic_sink"] != "point-item-score"
            or source_by_address[call]["candidate_disposition"] != "retain"
            or source_by_address[call]["proof_status"] != "unproved"
            for call in calls
        ):
            raise ValueError(f"source-ledger status mismatch for {profile['name']}")
        profiles.append(
            {
                "name": profile["name"],
                "difficulty_values": profile["difficulty_values"],
                "difficulty_names": profile["difficulty_names"],
                "entry_address": f"0x{profile['entry_address']:08x}",
                "helper_call_addresses": [f"0x{call:08x}" for call in calls],
                "base_obligation_ids": [base_by_address[call]["id"] for call in calls],
                "threshold": THRESHOLD,
                "top_score": profile["top_score"],
                "bottom_score": profile["bottom_score"],
                "position_multiplier": profile["position_multiplier"],
            }
        )

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
            "source_candidate_artifact_sha256": source_ledger["artifact_sha256"],
            "ftol2_helper_artifact_sha256": helper_audit["artifact_sha256"],
            "player_position_artifact_sha256": player_audit["artifact_sha256"],
        },
        "generator": {
            "path": "tools/item_score_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
            "x87_audit_sha256": arithmetic_obligations.sha256_file(
                tool_path.parent / "x87_audit.py"
            ),
            "disassembler": disassembler,
        },
        "mapped_function": function,
        "field_contract": {
            "item_current_position_y_offset": ITEM_Y_OFFSET,
            "load_width": "binary32",
            "first_and_second_load_are_same_field": True,
            "converted_result_projection": "signed EAX",
        },
        "difficulty_dispatch": {
            "table_address": f"0x{DIFFICULTY_TABLE_ADDRESS:08x}",
            "entries": [
                {
                    "difficulty_value": value,
                    "difficulty_name": name,
                    "target": f"0x{target:08x}",
                }
                for value, name, target in zip(
                    range(5), ["easy", "normal", "hard", "lunatic", "extra"], difficulty_targets
                )
            ],
        },
        "score_contract": {
            "profiles": profiles,
            "machine_formula": (
                "if signed_eax < 128 then top_score else "
                "bottom_score - ((signed_eax - 128) * position_multiplier), "
                "with each x86 integer operation wrapping to 32 bits"
            ),
            "gameplay_sink": "the selected itemScore is added to GameManager.score",
        },
        "checked_instruction_roles": instruction_rows,
        "model_contracts": {
            "score": "ZkTH06.ItemPointScore.score",
            "collision_interval": "ZkTH06.ItemPointScore.ordered_collection_bounds_item_y",
            "bounded_score": "ZkTH06.ItemPointScore.bounded_score_range",
            "signed_i32_safety": "ZkTH06.ItemPointScore.bounded_score_fits_signed_i32",
            "u32_score_addition": "ZkTH06.ItemPointScore.bounded_gameplay_score_addition",
            "total_coordinate_score": (
                "ZkTH06.ItemPointScore.collected_score_range_without_item_finiteness"
            ),
            "total_coordinate_u32_addition": (
                "ZkTH06.ItemPointScore."
                "collected_gameplay_score_addition_without_item_finiteness"
            ),
        },
        "evidence_status": (
            "static decode and derived difficulty/score facts; not a decoder proof, "
            "source correspondence theorem, proof of the player-position artifact's "
            "open obligations, helper refinement, or guest binding"
        ),
        "critical_nan_note": (
            "AABB separation comparisons are unordered-false on NaN, so collision success "
            "does not establish a finite item y. The total model instead requires the exact "
            "masked-invalid helper path, whose low-EAX observation is zero."
        ),
        "open_obligations": [
            "Prove or translation-validate the checked score blocks and difficulty table.",
            "Prove every reachable scoring difficulty is in the decoded 0..4 interval.",
            "Discharge the player-position artifact's candidate-NaN, writer, scheduling, and code bindings.",
            "Bind x87 AABB comparisons to the finite/infinity/NaN coordinate model.",
            "Prove both exact __ftol2 calls implement bounded truncation or invalid low-EAX zero.",
            "Prove the pre-update gameplay score satisfies the modeled 0..999999999 bound.",
            "Prove the guest score update refines the address-bound 32-bit score contract.",
        ],
        "counts": {
            "difficulty_entries": len(difficulty_targets),
            "score_profiles": len(profiles),
            "ftol2_calls": sum(len(profile["helper_calls"]) for profile in PROFILES),
            "checked_instruction_roles": len(instruction_rows),
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=Path("arithmetic/obligations-v1.json"))
    parser.add_argument(
        "--source-ledger",
        type=Path,
        default=Path("arithmetic/ftol2-source-candidates-v1.json"),
    )
    parser.add_argument(
        "--helper-audit",
        type=Path,
        default=Path("arithmetic/ftol2-helper-v1.json"),
    )
    parser.add_argument(
        "--player-audit",
        type=Path,
        default=Path("arithmetic/player-position-v1.json"),
    )
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    document = build_document(
        args.executable,
        args.mapping,
        load_sealed(args.ledger, "base arithmetic ledger"),
        load_sealed(args.source_ledger, "source-candidate ledger"),
        load_sealed(args.helper_audit, "__ftol2 helper audit"),
        load_sealed(args.player_audit, "player-position audit"),
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale item-score audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current item-score audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit retail instructions behind the closed Player shooting cadence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import player_position_audit
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.player-shooting-cadence-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION

MAPPED_FUNCTIONS = {
    "th06::Gui::HasCurrentMsgIdx": (0x004195A2, 0x1D),
    "th06::Supervisor::TickTimer": (0x00424285, 0x6E),
    "th06::Player::HandlePlayerInputs": (0x00427860, 0xD9A),
    "th06::Player::StartFireBulletTimer": (0x00428630, 0x45),
    "th06::Player::OnUpdate": (0x004288C0, 0x8EA),
    "th06::Player::UpdateFireBulletsTimer": (0x00429710, 0x10C),
    "th06::Player::SpawnBullets": (0x00429820, 0x10E),
    "th06::Player::AddedCallback": (0x00429C50, 0x45E),
}

SOURCE_ANCHORS = [
    ("src/Player.cpp", 117, "fireBulletCallback =", "fixed unfocused callback"),
    ("src/Player.cpp", 118, "fireBulletFocusCallback =", "fixed focused callback"),
    ("src/Player.cpp", 128, "fireBulletTimer.SetCurrent(-1)", "inactive timer anchor"),
    ("src/Player.cpp", 158, "if (g_GameManager.isTimeStopped)", "time-stop return"),
    ("src/Player.cpp", 325, "HandlePlayerInputs()", "input handler order"),
    ("src/Player.cpp", 328, "UpdatePlayerBullets(p)", "existing-bullet update order"),
    ("src/Player.cpp", 338, "UpdateFireBulletsTimer(p)", "fire timer update order"),
    ("src/Player.cpp", 680, "IS_PRESSED(TH_BUTTON_FOCUS)", "focus input"),
    ("src/Player.cpp", 682, "isFocus = true", "focused state"),
    ("src/Player.cpp", 686, "isFocus = false", "unfocused state"),
    ("src/Player.cpp", 928, "IS_PRESSED(TH_BUTTON_SHOOT)", "shoot/dialogue gate"),
    ("src/Player.cpp", 930, "StartFireBulletTimer", "timer start call"),
    ("src/Player.cpp", 932, "previousFrameInput =", "previous input writer"),
    ("src/Player.cpp", 981, "fireBulletTimer.AsFrames() < 0", "inactive start guard"),
    ("src/Player.cpp", 983, "InitializeForPopup", "timer start state"),
    ("src/Player.cpp", 989, "fireBulletTimer.AsFrames() < 0", "inactive update guard"),
    ("src/Player.cpp", 994, "fireBulletTimer.HasTicked()", "one-call cadence guard"),
    ("src/Player.cpp", 997, "SpawnBullets", "callback boundary"),
    ("src/Player.cpp", 1000, "fireBulletTimer.Tick()", "tick after callback"),
    ("src/Player.cpp", 1002, "fireBulletTimer.AsFrames() >= 30", "burst reset guard"),
    ("src/Player.cpp", 1005, "fireBulletTimer.SetCurrent(-1)", "burst reset"),
    ("src/Player.cpp", 1060, "if (!p->isFocus)", "callback selector"),
    ("src/Player.cpp", 1062, "fireBulletCallback", "unfocused callback call"),
    ("src/Player.cpp", 1066, "fireBulletFocusCallback", "focused callback call"),
    ("src/Gui.cpp", 794, "Gui::HasCurrentMsgIdx", "dialogue gate implementation"),
    ("src/Gui.cpp", 796, "currentMsgIdx", "dialogue-active predicate"),
    ("src/ZunTimer.hpp", 55, "InitializeForPopup", "timer initialization helper"),
    ("src/ZunTimer.hpp", 57, "current = 0", "start current"),
    ("src/ZunTimer.hpp", 58, "subFrame = 0", "start subframe"),
    ("src/ZunTimer.hpp", 59, "previous = -999", "start previous"),
    ("src/ZunTimer.hpp", 71, "previous = this->current", "tick ordering"),
    ("src/ZunTimer.hpp", 72, "TickTimer", "tick delegate"),
    ("src/ZunTimer.hpp", 87, "current != this->previous", "HasTicked predicate"),
]

# Operands are verified locally and intentionally omitted from the artifact.
EXPECTED_INSTRUCTIONS = {
    # Fixed callback selection and inactive anchor in AddedCallback.
    0x00429FC9: ("mov", "DWORD PTR [ecx+0x8],0xffffffff", "anchor timer current -1"),
    0x00429FD3: ("mov", "DWORD PTR [edx+0x4],0x0", "anchor timer subframe zero"),
    0x00429FDD: ("mov", "DWORD PTR [eax],0xfffffc19", "anchor timer previous -999"),
    0x0042A000: ("mov", "DWORD PTR [ecx+0x75dc],edx", "store fixed unfocused callback"),
    0x0042A022: ("mov", "DWORD PTR [eax+0x75e0],ecx", "store fixed focused callback"),
    # OnUpdate ordering after the enclosing state gate.
    0x0042910F: ("call", "0x427860", "call HandlePlayerInputs"),
    0x00429127: ("call", "0x4291b0", "update existing player bullets"),
    0x00429199: ("call", "0x429710", "update fire timer last"),
    # Focus derivation and shoot/dialogue/start gate.
    0x004279AB: ("mov", "cx,WORD PTR ds:0x69d904", "load input for focus"),
    0x004279B2: ("and", "ecx,0x4", "mask focus bit"),
    0x004279BF: ("mov", "BYTE PTR [edx+0x9e3],0x1", "store focused"),
    0x004279CE: ("mov", "BYTE PTR [eax+0x9e3],0x0", "store unfocused"),
    0x004285B7: ("mov", "ax,ds:0x69d904", "load input for shoot"),
    0x004285BD: ("and", "eax,0x1", "mask shoot bit"),
    0x004285C9: ("call", "0x4195a2", "query dialogue gate"),
    0x004285D0: ("jne", "0x4285e1", "suppress start during dialogue"),
    0x004285D9: ("call", "0x428630", "start fire timer"),
    0x004285E7: ("mov", "ax,ds:0x69d904", "reload current input"),
    0x004285ED: ("mov", "WORD PTR [edx+0xa18],ax", "store previous frame input"),
    # Dialogue predicate itself.
    0x004195AC: ("mov", "eax,DWORD PTR [eax+0x4]", "load Gui implementation"),
    0x004195B1: ("cmp", "DWORD PTR [eax+0x253c],0x0", "test current message index"),
    0x004195B8: ("setge", "cl", "return active-message predicate"),
    # StartFireBulletTimer / InitializeForPopup.
    0x00428639: ("mov", "ecx,DWORD PTR [eax+0x75b0]", "load fire timer current"),
    0x00428642: ("cmp", "DWORD PTR [ebp-0x4],0x0", "test inactive timer"),
    0x00428646: ("jge", "0x428671", "leave active timer unchanged"),
    0x00428657: ("mov", "DWORD PTR [eax+0x8],0x0", "start current at zero"),
    0x00428661: ("mov", "DWORD PTR [ecx+0x4],0x0", "start subframe at zero"),
    0x0042866B: ("mov", "DWORD PTR [edx],0xfffffc19", "start previous at -999"),
    # UpdateFireBulletsTimer cadence, callback, tick, and reset.
    0x00429719: ("mov", "ecx,DWORD PTR [eax+0x75b0]", "load current for inactive guard"),
    0x00429722: ("cmp", "DWORD PTR [ebp-0x4],0x0", "test inactive update"),
    0x00429726: ("jge", "0x42972f", "continue active update"),
    0x00429741: ("mov", "edx,DWORD PTR [eax+0x8]", "load current for HasTicked"),
    0x00429746: ("cmp", "edx,DWORD PTR [ecx]", "compare current and previous"),
    0x00429748: ("setne", "al", "derive HasTicked"),
    0x0042974D: ("je", "0x42978e", "skip callback when not ticked"),
    0x0042974F: ("cmp", "DWORD PTR ds:0x6d1bf0,0x0", "active bomb callback gate"),
    0x00429760: ("cmp", "ecx,0x1", "Marisa bomb gate"),
    0x0042976D: ("cmp", "edx,0x1", "shot-B bomb gate"),
    0x0042977E: ("mov", "edx,DWORD PTR [ebp-0xc]", "load callback timer argument"),
    0x00429786: ("call", "0x429820", "call SpawnBullets boundary"),
    0x004297A0: ("mov", "ecx,DWORD PTR [eax+0x8]", "load timer current before tick"),
    0x004297A3: ("mov", "DWORD PTR [edx],ecx", "copy current to previous"),
    0x004297B8: ("call", "0x424285", "tick through Supervisor"),
    0x004297C9: ("cmp", "DWORD PTR [ebp-0x14],0x1e", "test timer limit 30"),
    0x004297CD: ("jge", "0x4297ed", "take timer reset path"),
    0x004297D9: ("cmp", "ecx,0x2", "dead-state reset gate"),
    0x004297E8: ("cmp", "eax,0x1", "spawning-state reset gate"),
    0x004297FC: ("mov", "DWORD PTR [edx+0x8],0xffffffff", "reset timer current -1"),
    0x00429806: ("mov", "DWORD PTR [eax+0x4],0x0", "reset timer subframe zero"),
    0x00429810: ("mov", "DWORD PTR [ecx],0xfffffc19", "reset timer previous -999"),
    # Stop at, but make explicit, the character callback dispatch boundary.
    0x00429873: ("movsx", "eax,BYTE PTR [edx+0x9e3]", "load focus for callback choice"),
    0x0042987C: ("jne", "0x42989f", "select focused callback"),
    0x00429891: ("call", "DWORD PTR [edx+0x75c0]", "call fixed unfocused callback"),
    0x004298B2: ("call", "DWORD PTR [ecx+0x75c4]", "call fixed focused callback"),
}


def load_sealed(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"input artifact has an invalid digest: {path}")
    return document


def verify_sources(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blobs: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for source_file, line, anchor, role in SOURCE_ANCHORS:
        if source_file not in blobs:
            blobs[source_file] = player_position_audit.pinned_blob(source_root, source_file)
        lines = blobs[source_file].decode("utf-8").splitlines()
        if line <= 0 or line > len(lines) or anchor not in lines[line - 1]:
            raise ValueError(f"source anchor mismatch at {source_file}:{line}: {anchor!r}")
        rows.append({"file": source_file, "line": line, "anchor": anchor, "role": role})
    return rows, {
        source_file: hashlib.sha256(blob).hexdigest()
        for source_file, blob in sorted(blobs.items())
    }


def verify_functions(mapping_path: Path) -> list[dict[str, Any]]:
    by_name = {function.name: function for function in x87_audit.load_mapping(mapping_path)}
    rows: list[dict[str, Any]] = []
    for name, (start, size) in MAPPED_FUNCTIONS.items():
        function = by_name.get(name)
        if function is None or (function.start, function.size) != (start, size):
            got = None if function is None else (function.start, function.size)
            raise ValueError(f"mapping mismatch for {name}: got {got}")
        rows.append({"name": name, "start": f"0x{start:08x}", "size": size})
    return rows


def verify_instructions(disassembly: str) -> list[dict[str, str]]:
    instructions = {
        instruction.address: instruction for instruction in x87_audit.parse_disassembly(disassembly)
    }
    rows: list[dict[str, str]] = []
    for address, (mnemonic, operands, role) in EXPECTED_INSTRUCTIONS.items():
        instruction = instructions.get(address)
        if instruction is None:
            raise ValueError(f"missing shooting instruction at 0x{address:08x}")
        if (instruction.mnemonic, instruction.operands) != (mnemonic, operands):
            raise ValueError(
                f"instruction mismatch at 0x{address:08x}: got "
                f"{instruction.mnemonic} {instruction.operands!r}, expected "
                f"{mnemonic} {operands!r}"
            )
        rows.append({"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role})
    return rows


def build_document(
    executable: Path,
    mapping_path: Path,
    enclosing: dict[str, Any],
    source_root: Path,
    objdump: str,
    tool_path: Path,
) -> dict[str, Any]:
    executable_hash = arithmetic_obligations.sha256_file(executable)
    mapping_hash = arithmetic_obligations.sha256_file(mapping_path)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable does not match the pinned Japanese v1.02h image")
    if mapping_hash != arithmetic_obligations.PINNED_MAPPING_SHA256:
        raise ValueError("mapping does not match the pinned authoritative mapping")
    if enclosing.get("kind") != "zkth06.enclosing-player-state-audit":
        raise ValueError("selected enclosing-state artifact has the wrong kind")
    if enclosing.get("inputs", {}).get("executable_sha256") != executable_hash:
        raise ValueError("enclosing-state artifact is bound to a different executable")

    source_anchors, source_hashes = verify_sources(source_root)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instructions(disassembly)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "enclosing_player_state_artifact_sha256": enclosing["artifact_sha256"],
        },
        "generator": {
            "path": "tools/player_shooting_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
            "x87_audit_sha256": arithmetic_obligations.sha256_file(tool_path.parent / "x87_audit.py"),
            "disassembler": disassembler,
        },
        "upstream": {
            "url": UPSTREAM_URL,
            "revision": UPSTREAM_REVISION,
            "source_files": source_hashes,
            "anchors": source_anchors,
            "correspondence_status": "manual-disassembly-source-alignment-unproved",
        },
        "mapped_functions": verify_functions(mapping_path),
        "checked_instruction_roles": instruction_rows,
        "derived_profile_contract": {
            "profile": "full-speed-no-dialogue-no-bomb-no-hit-no-time-stop-write",
            "anchor": {
                "is_focus": 0,
                "previous_frame_input": 0,
                "fire_timer_previous": -999,
                "fire_timer_subframe_bits": "0x00000000",
                "fire_timer_current": -1,
            },
            "shoot_input_mask": "0x0001",
            "focus_input_mask": "0x0004",
            "inactive_timer": {"previous": -999, "current": -1},
            "timer_start": {"previous": -999, "subframe_bits": "0x00000000", "current": 0},
            "spawn_condition": "timer current is nonnegative, current differs from previous, and Marisa-B bomb suppression is false",
            "spawn_effect": "one call to Player::SpawnBullets(player, current timer), followed by timer tick",
            "full_speed_tick": "previous becomes current; current increments by one; subframe remains +0",
            "reset_condition": "post-tick current >= 30, dead state, or spawning state",
            "callback_choice": "isFocus selects the fixed character/shot callback inside SpawnBullets",
            "dialogue_gate": "currentMsgIdx >= 0 suppresses timer start; selected dynamic profile fixes this predicate false",
            "enclosing_player_state_artifact_sha256": enclosing["artifact_sha256"],
            "refinement_boundary": "ends at character callback dispatch; bullet allocation and callback geometry are not modeled",
        },
        "evidence_status": (
            "exact static signatures and pinned source candidates for the no-dialogue shooting "
            "cadence through character callback dispatch, bound to the enclosing player-state "
            "audit; not verified decoding, compiler correspondence, reachability, complete writer "
            "analysis, callback geometry, or guest refinement"
        ),
        "open_obligations": [
            "Prove or translation-validate each checked instruction and source alignment.",
            "Prove the no-dialogue predicate and complete writer noninterference for the selected replay interval.",
            "Prove UpdatePlayerBullets and intervening animation calls do not write the projected shooting state.",
            "Refine character callback dispatch into bullet-slot allocation and shot-specific geometry.",
            "Prove the Rust shooting transition refines this address-bound profile contract.",
        ],
        "counts": {
            "mapped_functions": len(MAPPED_FUNCTIONS),
            "source_anchors": len(source_anchors),
            "checked_instruction_roles": len(instruction_rows),
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--mapping", type=Path, default=Path("repos/th06/config/mapping.csv"))
    parser.add_argument(
        "--enclosing-state",
        type=Path,
        default=Path("arithmetic/player-state-enclosing-v1.json"),
    )
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    document = build_document(
        args.executable,
        args.mapping,
        load_sealed(args.enclosing_state),
        args.source_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale player-shooting audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current player-shooting audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

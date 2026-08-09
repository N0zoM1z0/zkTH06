#!/usr/bin/env python3
"""Audit the pinned retail instructions behind the first enclosing player state."""

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
KIND = "zkth06.enclosing-player-state-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION

MAPPED_FUNCTIONS = {
    "th06::ZunTimer::Decrement": (0x004241E5, 0xA0),
    "th06::Supervisor::TickTimer": (0x00424285, 0x6E),
    "th06::Player::HandlePlayerInputs": (0x00427860, 0xD9A),
    "th06::Player::OnUpdate": (0x004288C0, 0x8EA),
    "th06::Player::AddedCallback": (0x00429C50, 0x45E),
}

SOURCE_ANCHORS = [
    ("src/Player.cpp", 27, "DIFFABLE_STATIC_ARRAY_ASSIGN(CharacterData, 4, g_CharData)", "fixed character table"),
    ("src/Player.cpp", 98, "positionCenter.x = g_GameManager.arcadeRegionSize.x / 2.0f", "initial x"),
    ("src/Player.cpp", 99, "positionCenter.y = g_GameManager.arcadeRegionSize.y - 64.0f", "initial y"),
    ("src/Player.cpp", 114, "memcpy(&p->characterData", "copy fixed character record"),
    ("src/Player.cpp", 115, "diagonalMovementSpeed =", "derive diagonal speed"),
    ("src/Player.cpp", 119, "playerState = PLAYER_STATE_SPAWNING", "initial player state"),
    ("src/Player.cpp", 120, "invulnerabilityTimer.SetCurrent(120)", "initial timer"),
    ("src/Player.cpp", 131, "bombInfo.isInUse = 0", "initial bomb state"),
    ("src/Player.cpp", 136, "verticalMovementSpeedMultiplierDuringBomb = 1.0", "initial vertical multiplier"),
    ("src/Player.cpp", 137, "horizontalMovementSpeedMultiplierDuringBomb = 1.0", "initial horizontal multiplier"),
    ("src/Player.cpp", 158, "if (g_GameManager.isTimeStopped)", "time-stop return precedes player update"),
    ("src/Player.cpp", 170, "if (p->bombInfo.isInUse)", "bomb callback precedes state timer"),
    ("src/Player.cpp", 174, "else if (!g_Gui.HasCurrentMsgIdx()", "bomb-input writer"),
    ("src/Player.cpp", 278, "verticalMovementSpeedMultiplierDuringBomb = 1.0", "spawn multiplier reset"),
    ("src/Player.cpp", 284, "playerState = PLAYER_STATE_INVULNERABLE", "spawn-to-invulnerable transition"),
    ("src/Player.cpp", 289, "invulnerabilityTimer.SetCurrent(240)", "invulnerability timer reset"),
    ("src/Player.cpp", 290, "respawnTimer = 6", "post-spawn bomb eligibility"),
    ("src/Player.cpp", 298, "if (p->playerState == PLAYER_STATE_INVULNERABLE)", "invulnerable branch"),
    ("src/Player.cpp", 300, "invulnerabilityTimer.Decrement(1)", "invulnerability decrement"),
    ("src/Player.cpp", 303, "playerState = PLAYER_STATE_ALIVE", "invulnerable-to-alive transition"),
    ("src/Player.cpp", 304, "invulnerabilityTimer.SetCurrent(0)", "alive timer reset"),
    ("src/Player.cpp", 321, "invulnerabilityTimer.Tick()", "alive timer tick"),
    ("src/Player.cpp", 323, "playerState != PLAYER_STATE_DEAD", "movement state gate"),
    ("src/Player.cpp", 325, "HandlePlayerInputs()", "movement call"),
    ("src/ZunTimer.cpp", 43, "framerateMultiplier > 0.99f", "full-speed decrement branch"),
    ("src/ZunTimer.cpp", 45, "current = this->current - value", "full-speed integer decrement"),
    ("src/ZunTimer.hpp", 71, "previous = this->current", "timer previous update"),
    ("src/ZunTimer.hpp", 72, "TickTimer(&this->current, &this->subFrame)", "timer tick delegate"),
    ("src/Supervisor.cpp", 550, "framerateMultiplier <= 0.99f", "fractional tick branch"),
    ("src/Supervisor.cpp", 561, "*frames = *frames + 1", "full-speed integer tick"),
]

# Operands are checked locally but deliberately omitted from the tracked artifact.
EXPECTED_INSTRUCTIONS = {
    # AddedCallback fixes the state used by the pre-game spawn sequence.
    0x00429EC4: ("mov", "BYTE PTR [eax+0x9e0],0x1", "initialize spawning state"),
    0x00429EDA: ("mov", "DWORD PTR [edx+0x8],0x78", "initialize timer current to 120"),
    0x00429EE4: ("mov", "DWORD PTR [eax+0x4],0x0", "initialize timer subframe to zero"),
    0x00429EEE: ("mov", "DWORD PTR [ecx],0xfffffc19", "initialize timer previous to -999"),
    0x0042A02B: ("mov", "DWORD PTR [edx+0x75c8],0x0", "initialize bomb inactive"),
    0x0042A082: ("mov", "DWORD PTR [ecx+0x9d4],0x3f800000", "initialize vertical bomb multiplier to one"),
    0x0042A08F: ("mov", "DWORD PTR [edx+0x9d0],0x3f800000", "initialize horizontal bomb multiplier to one"),
    0x0042A09C: ("mov", "DWORD PTR [eax+0x9d8],0x8", "initialize respawn timer to eight"),
    # OnUpdate ordering and the unsupported bomb writer boundary.
    0x004288C6: ("movsx", "eax,BYTE PTR ds:0x69bccc", "load time-stop flag first"),
    0x004288CD: ("test", "eax,eax", "test time-stop flag"),
    0x004288CF: ("je", "0x4288db", "continue only when time is running"),
    0x004288D1: ("mov", "eax,0x1", "time-stop callback result"),
    0x0042893A: ("cmp", "DWORD PTR [ecx+0x75c8],0x0", "test active bomb before state timer"),
    0x00428941: ("je", "0x428958", "take no-active-bomb path"),
    0x0042894A: ("call", "DWORD PTR [eax+0x75dc]", "active bomb callback writer"),
    0x0042898B: ("mov", "ax,ds:0x69d904", "load current replay input for bomb test"),
    0x00428991: ("and", "eax,0x2", "mask bomb input"),
    # The post-spawn frame constructs the fixed proof anchor, then decrements it.
    0x00428F38: ("mov", "BYTE PTR [eax+0x9e0],0x3", "enter invulnerable state"),
    0x00428F81: ("mov", "DWORD PTR [edx+0x8],0xf0", "set invulnerability timer to 240"),
    0x00428F8B: ("mov", "DWORD PTR [eax+0x4],0x0", "reset invulnerability subframe"),
    0x00428F95: ("mov", "DWORD PTR [ecx],0xfffffc19", "reset invulnerability previous"),
    0x00428F9E: ("mov", "DWORD PTR [edx+0x9d8],0x6", "set post-spawn respawn timer"),
    0x00428FD8: ("movsx", "edx,BYTE PTR [ecx+0x9e0]", "load life state for timer branch"),
    0x00428FDF: ("cmp", "edx,0x3", "select invulnerable branch"),
    0x00428FE8: ("push", "0x1", "decrement timer by one"),
    0x00428FF3: ("call", "0x4241e5", "call ZunTimer Decrement"),
    0x00428FFB: ("mov", "ecx,DWORD PTR [eax+0x75bc]", "load decremented current timer"),
    0x00429004: ("cmp", "DWORD PTR [ebp-0x44],0x0", "test timer exhaustion"),
    0x00429008: ("jg", "0x42905d", "remain invulnerable while positive"),
    0x0042900D: ("mov", "BYTE PTR [edx+0x9e0],0x0", "enter alive state"),
    0x00429022: ("mov", "DWORD PTR [ecx+0x8],0x0", "reset alive timer current"),
    0x0042902C: ("mov", "DWORD PTR [edx+0x4],0x0", "reset alive timer subframe"),
    0x00429036: ("mov", "DWORD PTR [eax],0xfffffc19", "reset alive timer previous"),
    # Alive ticks and both accepted life states reach movement.
    0x004290D1: ("mov", "ecx,DWORD PTR [eax+0x8]", "load current timer before tick"),
    0x004290D4: ("mov", "DWORD PTR [edx],ecx", "copy current timer to previous"),
    0x004290E9: ("call", "0x424285", "call Supervisor TickTimer"),
    0x004290F1: ("movsx", "edx,BYTE PTR [ecx+0x9e0]", "load state for dead gate"),
    0x004290F8: ("cmp", "edx,0x2", "reject dead movement"),
    0x00429100: ("movsx", "ecx,BYTE PTR [eax+0x9e0]", "load state for spawning gate"),
    0x00429107: ("cmp", "ecx,0x1", "reject spawning movement"),
    0x0042910F: ("call", "0x427860", "call HandlePlayerInputs"),
    # At the replay-fixed 1.0 rate, timer operations take their integer paths.
    0x004241ED: ("fld", "DWORD PTR ds:0x6c6ec4", "load configured rate for decrement"),
    0x004241F3: ("fcomp", "DWORD PTR ds:0x46b734", "compare decrement rate with binary32 0.99"),
    0x004241FB: ("test", "ah,0x41", "select greater-than rate relation"),
    0x004241FE: ("jne", "0x424211", "leave integer decrement only for non-greater rate"),
    0x00424203: ("mov", "eax,DWORD PTR [eax+0x8]", "load timer current for integer decrement"),
    0x00424206: ("sub", "eax,DWORD PTR [ebp+0x8]", "subtract decrement amount"),
    0x0042420C: ("mov", "DWORD PTR [ecx+0x8],eax", "store integer decrement"),
    0x0042428F: ("fld", "DWORD PTR [eax+0x1ac]", "load configured rate for tick"),
    0x00424295: ("fcomp", "DWORD PTR ds:0x46b734", "compare tick rate with binary32 0.99"),
    0x0042429D: ("test", "ah,0x41", "select tick rate relation"),
    0x004242A0: ("jp", "0x4242e4", "select full-speed integer tick"),
    0x004242E7: ("mov", "eax,DWORD PTR [eax]", "load timer current for integer tick"),
    0x004242E9: ("inc", "eax", "increment timer current"),
    0x004242ED: ("mov", "DWORD PTR [ecx],eax", "store integer tick"),
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
    hashes = {
        source_file: hashlib.sha256(blob).hexdigest()
        for source_file, blob in sorted(blobs.items())
    }
    return rows, hashes


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
            raise ValueError(f"missing enclosing-state instruction at 0x{address:08x}")
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
    player_position: dict[str, Any],
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
    if player_position.get("kind") != player_position_audit.KIND:
        raise ValueError("selected player-position artifact has the wrong kind")
    if player_position.get("inputs", {}).get("executable_sha256") != executable_hash:
        raise ValueError("player-position artifact is bound to a different executable")

    source_anchors, source_hashes = verify_sources(source_root)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instructions(disassembly)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "player_position_artifact_sha256": player_position["artifact_sha256"],
        },
        "generator": {
            "path": "tools/player_state_enclosing_audit.py",
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
            "profile": "full-speed-no-bomb-no-hit-no-time-stop-write",
            "anchor": {
                "game_frame": 1,
                "player_state": 3,
                "invulnerability_timer": 239,
                "timer_subframe_bits": "0x00000000",
                "bomb_active": 0,
                "position_x_bits": "0x43400000",
                "position_y_bits": "0x43c00000",
            },
            "full_speed_rate_bits": "0x3f800000",
            "inactive_bomb_multiplier_bits": "0x3f800000",
            "invulnerable_step": "positive timer decrements by one; zero enters alive and resets timer",
            "alive_step": "timer increments by one",
            "time_stop_step": "return before bomb, timer, and movement",
            "movement_state_gate": "alive and invulnerable states call HandlePlayerInputs",
            "fixed_motion_contract_artifact_sha256": player_position["artifact_sha256"],
            "unsupported_writers_fail_closed": [
                "bomb activation or active bomb callback",
                "collision death and respawn",
                "ECL or other time-stop writes",
                "non-full-speed timer arithmetic",
            ],
        },
        "evidence_status": (
            "exact static signatures and pinned source candidates for the closed profile, plus "
            "a direct binding to the fixed position/speed/bounds audit; not verified decoding, "
            "compiler correspondence, reachability, complete writer analysis, or guest refinement"
        ),
        "open_obligations": [
            "Prove or translation-validate each checked instruction and source alignment.",
            "Derive the post-calc frame-one anchor from registration and the pre-stage update schedule.",
            "Prove complete writer exclusion for time stop, player life state, timer, bomb state, and multipliers under the selected route.",
            "Extend the transition to collision death, spawning, respawn, bombs, and non-full-speed timer arithmetic.",
            "Prove the Rust enclosing transition refines the address-bound profile contract.",
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
        "--player-position",
        type=Path,
        default=Path("arithmetic/player-position-v1.json"),
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
        load_sealed(args.player_position),
        args.source_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale enclosing player-state audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current enclosing player-state audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit the pinned player-y initialization, clamp, grab box, and item collision."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import run_ftol2_probe
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.player-position-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = "cc475a0bc3fef38683b0f02224c87ddba0a021d9"

MAPPED_FUNCTIONS = {
    "th06::BombData::BombMarisaBCalc": (0x00406E70, 0x33E),
    "th06::GameManager::AddedCallback": (0x0041BB02, 0x6F5),
    "th06::GameWindow::Render": (0x004206E0, 0x466),
    "th06::Player::CalcItemBoxCollision": (0x00426FD0, 0x1BA),
    "th06::Player::HandlePlayerInputs": (0x00427860, 0xD9A),
    "th06::Player::OnUpdate": (0x004288C0, 0x8EA),
    "th06::Player::AddedCallback": (0x00429C50, 0x45E),
    "th06::ReplayManager::RegisterChain": (0x0042A240, 0x228),
}

SOURCE_ANCHORS = [
    ("src/GameManager.cpp", 289, "arcadeRegionSize.y = 448.0", "arcade height"),
    ("src/GameManager.cpp", 291, "playerMovementAreaTopLeftPos.y = 16.0", "movement lower bound"),
    ("src/GameManager.cpp", 293, "playerMovementAreaSize.y = 416.0", "movement height"),
    ("src/Player.cpp", 99, "positionCenter.y = g_GameManager.arcadeRegionSize.y - 64.0f", "initial y"),
    ("src/Player.cpp", 111, "grabItemSize.y = 12.0", "grab radius"),
    ("src/Player.cpp", 115, "diagonalMovementSpeed =", "diagonal speed initialization"),
    ("src/Player.cpp", 116, "diagonalMovementSpeedFocus =", "focused diagonal speed initialization"),
    ("src/Player.cpp", 136, "verticalMovementSpeedMultiplierDuringBomb = 1.0", "initial bomb multiplier"),
    ("src/Player.cpp", 242, "positionCenter.y = g_GameManager.arcadeRegionSize.y - 64.0f", "respawn y"),
    ("src/Player.cpp", 278, "verticalMovementSpeedMultiplierDuringBomb = 1.0", "spawn bomb multiplier"),
    ("src/Player.cpp", 801, "verticalSpeed * this->verticalMovementSpeedMultiplierDuringBomb", "movement candidate"),
    ("src/Player.cpp", 813, "positionCenter.y < g_GameManager.playerMovementAreaTopLeftPos.y", "lower clamp"),
    ("src/Player.cpp", 817, "playerMovementAreaTopLeftPos.y + g_GameManager.playerMovementAreaSize.y <", "upper clamp"),
    ("src/Player.cpp", 827, "grabItemTopLeft = this->positionCenter - this->grabItemSize", "grab top"),
    ("src/Player.cpp", 829, "grabItemBottomRight = this->positionCenter + this->grabItemSize", "grab bottom"),
    ("src/Player.cpp", 1365, "grabItemTopLeft.y > itemBottomRight.y", "vertical item collision"),
    ("src/BombData.cpp", 473, "verticalMovementSpeedMultiplierDuringBomb = 1.0f", "bomb-end multiplier"),
    ("src/BombData.cpp", 491, "verticalMovementSpeedMultiplierDuringBomb = 0.3f", "Marisa-B multiplier"),
    ("src/ReplayManager.cpp", 81, "framerateMultiplier = 1.0f", "replay rate"),
    ("src/GameWindow.cpp", 139, "effectiveFramerateMultiplier = delta", "adaptive effective rate"),
    ("src/GameWindow.cpp", 147, "effectiveFramerateMultiplier = g_Supervisor.framerateMultiplier", "copied effective rate"),
]

BINARY32_CONSTANTS = {
    0x0046A2B4: (0x41800000, "16", "movement lower bound"),
    0x0046A7BC: (0x43E00000, "448", "arcade height"),
    0x0046A7EC: (0x43D00000, "416", "movement height"),
    0x0046A440: (0x42800000, "64", "spawn offset"),
    0x0046A44C: (0x40000000, "2", "horizontal center divisor and sqrt input"),
}

CHARACTER_SPEED_TABLE = 0x00476728
CHARACTER_SPEED_RECORD_SIZE = 0x18
EXPECTED_CHARACTER_SPEEDS = [
    [0x40800000, 0x40000000, 0x40800000, 0x40000000],
    [0x40800000, 0x40000000, 0x40800000, 0x40000000],
    [0x40A00000, 0x40200000, 0x40A00000, 0x40200000],
    [0x40A00000, 0x40200000, 0x40A00000, 0x40200000],
]

EXPECTED_INSTRUCTIONS = {
    # The identified gameplay bomb callback that changes movement multipliers.
    0x00406EA8: ("mov", "edx,DWORD PTR [ebp+0x8]", "load player at Marisa-B bomb end"),
    0x00406EAB: ("mov", "DWORD PTR [edx+0x9d4],0x3f800000", "restore vertical multiplier 1"),
    0x00406FD5: ("mov", "ecx,DWORD PTR [ebp+0x8]", "load player at Marisa-B bomb start"),
    0x00406FD8: ("mov", "DWORD PTR [ecx+0x9d4],0x3e99999a", "set vertical multiplier binary32 0.3"),
    # Game-region y constants.
    0x0041BB6C: ("mov", "eax,DWORD PTR [ebp+0x8]", "load GameManager for arcade height"),
    0x0041BB6F: ("fld", "DWORD PTR ds:0x46a7bc", "load arcade height 448"),
    0x0041BB75: ("fstp", "DWORD PTR [eax+0x1a48]", "store arcade height"),
    0x0041BB8A: ("mov", "eax,DWORD PTR [ebp+0x8]", "load GameManager for movement lower bound"),
    0x0041BB8D: ("fld", "DWORD PTR ds:0x46a2b4", "load movement lower bound 16"),
    0x0041BB93: ("fstp", "DWORD PTR [eax+0x1a50]", "store movement lower bound"),
    0x0041BBA8: ("mov", "eax,DWORD PTR [ebp+0x8]", "load GameManager for movement height"),
    0x0041BBAB: ("fld", "DWORD PTR ds:0x46a7ec", "load movement height 416"),
    0x0041BBB1: ("fstp", "DWORD PTR [eax+0x1a58]", "store movement height"),
    # The original timing path publishes its selected effective multiplier here.
    0x00420AF8: ("fld", "QWORD PTR [ebp-0x38]", "load adaptive rate bucket"),
    0x00420AFB: ("fstp", "DWORD PTR ds:0x6c6ec0", "store adaptive effective multiplier"),
    0x00420B1E: ("mov", "edx,DWORD PTR ds:0x6c6ec4", "load configured framerate multiplier"),
    0x00420B24: ("mov", "DWORD PTR ds:0x6c6ec0,edx", "copy configured multiplier to effective multiplier"),
    # Item collision accepts only alive/invulnerable states and uses two y comparisons.
    0x00426FE5: ("movsx", "ecx,BYTE PTR [eax+0x9e0]", "load player state"),
    0x00426FEC: ("test", "ecx,ecx", "test alive state zero"),
    0x00426FEE: ("je", "0x427009", "allow alive player"),
    0x00426FF6: ("movsx", "eax,BYTE PTR [edx+0x9e0]", "reload player state"),
    0x00426FFD: ("cmp", "eax,0x3", "test invulnerable state three"),
    0x00427000: ("je", "0x427009", "allow invulnerable player"),
    0x00427153: ("fld", "DWORD PTR [eax+0x474]", "load grab top y"),
    0x00427159: ("fcomp", "DWORD PTR [ebp-0x8]", "compare grab top y with item bottom y"),
    0x0042715C: ("fnstsw", "ax", "publish first y comparison status"),
    0x0042715E: ("and", "eax,0x4100", "select C0/C3 for first y comparison"),
    0x00427163: ("je", "0x42717b", "reject when grab top is greater"),
    0x00427165: ("mov", "ecx,DWORD PTR [ebp-0x84]", "load player for grab bottom y"),
    0x0042716B: ("fld", "DWORD PTR [ecx+0x480]", "load grab bottom y"),
    0x00427171: ("fcomp", "DWORD PTR [ebp-0x14]", "compare grab bottom y with item top y"),
    0x00427174: ("fnstsw", "ax", "publish second y comparison status"),
    0x00427176: ("test", "ah,0x5", "select C0/C2 for second y comparison"),
    0x00427179: ("jp", "0x42717f", "accept non-separated or unordered y"),
    # Vertical movement candidate and ordered lower/upper clamp.
    0x00427DD8: ("fld", "DWORD PTR [ebp-0x8]", "load selected vertical speed"),
    0x00427DDB: ("fmul", "DWORD PTR [ecx+0x9d4]", "multiply bomb movement factor"),
    0x00427DE1: ("fmul", "DWORD PTR ds:0x6c6ec0", "multiply effective frame factor"),
    0x00427DED: ("fadd", "DWORD PTR [edx]", "add prior player y"),
    0x00427DF5: ("fstp", "DWORD PTR [eax]", "store binary32 movement candidate y"),
    0x00427E60: ("fld", "DWORD PTR [eax+0x444]", "load candidate y for lower clamp"),
    0x00427E66: ("fcomp", "DWORD PTR ds:0x69d6f0", "compare candidate y with lower 16"),
    0x00427E6C: ("fnstsw", "ax", "publish lower-clamp status"),
    0x00427E6E: ("test", "ah,0x5", "select C0/C2 for lower clamp"),
    0x00427E71: ("jp", "0x427e87", "skip lower assignment unless candidate is less"),
    0x00427E79: ("mov", "edx,DWORD PTR ds:0x69d6f0", "load lower-bound bits"),
    0x00427E7F: ("mov", "DWORD PTR [ecx+0x444],edx", "assign lower-bound y"),
    0x00427E87: ("fld", "DWORD PTR ds:0x69d6f0", "load upper-bound base 16"),
    0x00427E8D: ("fadd", "DWORD PTR ds:0x69d6f8", "add movement height 416"),
    0x00427E99: ("fcomp", "DWORD PTR [eax+0x444]", "compare upper 432 with candidate y"),
    0x00427E9F: ("fnstsw", "ax", "publish upper-clamp status"),
    0x00427EA1: ("test", "ah,0x5", "select C0/C2 for upper clamp"),
    0x00427EA4: ("jp", "0x427ebe", "skip upper assignment unless upper is less"),
    0x00427EA6: ("fld", "DWORD PTR ds:0x69d6f0", "reload upper-bound base"),
    0x00427EAC: ("fadd", "DWORD PTR ds:0x69d6f8", "recompute upper 432"),
    0x00427EB8: ("fstp", "DWORD PTR [ecx+0x444]", "assign upper-bound y"),
    # Radius-12 grab box y dataflow.
    0x00427FF4: ("fld", "DWORD PTR [edx+0x4]", "load clamped player y for grab top"),
    0x00427FF7: ("fsub", "DWORD PTR [eax+0x4]", "subtract grab radius y"),
    0x00427FFA: ("fstp", "DWORD PTR [ebp-0x88]", "store grab top y temporary"),
    0x0042801F: ("mov", "ecx,DWORD PTR [ebp-0x88]", "load grab top y bits"),
    0x00428025: ("mov", "DWORD PTR [ebp-0x38],ecx", "carry grab top y bits"),
    0x00428041: ("mov", "edx,DWORD PTR [ebp-0x38]", "reload grab top y bits"),
    0x00428044: ("mov", "DWORD PTR [eax+0x4],edx", "store grab top y"),
    0x00428094: ("fld", "DWORD PTR [eax+0x4]", "load clamped player y for grab bottom"),
    0x00428097: ("fadd", "DWORD PTR [ecx+0x4]", "add grab radius y"),
    0x0042809A: ("fstp", "DWORD PTR [ebp-0x9c]", "store grab bottom y temporary"),
    0x004280BF: ("mov", "edx,DWORD PTR [ebp-0x9c]", "load grab bottom y bits"),
    0x004280C5: ("mov", "DWORD PTR [ebp-0x44],edx", "carry grab bottom y bits"),
    0x004280E2: ("mov", "eax,DWORD PTR [ebp-0x44]", "reload grab bottom y bits"),
    0x004280E5: ("mov", "DWORD PTR [ecx+0x4],eax", "store grab bottom y"),
    # Respawn and spawning reset.
    0x00428D3F: ("fld", "DWORD PTR ds:0x69d6e8", "load arcade height for respawn"),
    0x00428D45: ("fsub", "DWORD PTR ds:0x46a440", "subtract respawn offset 64"),
    0x00428D4E: ("fstp", "DWORD PTR [eax+0x444]", "store respawn y 384"),
    0x00428ED4: ("mov", "DWORD PTR [ecx+0x9d4],0x3f800000", "restore spawning vertical multiplier 1"),
    # Initial position, radius, character speeds, and multiplier.
    0x00429D55: ("fld", "DWORD PTR ds:0x69d6e8", "load arcade height for initial y"),
    0x00429D5B: ("fsub", "DWORD PTR ds:0x46a440", "subtract initial offset 64"),
    0x00429D64: ("fstp", "DWORD PTR [ecx+0x444]", "store initial y 384"),
    0x00429DF6: ("mov", "DWORD PTR [eax+0x498],0x41400000", "store grab radius y 12"),
    0x00429E2F: ("add", "esi,0x476728", "select character speed table record"),
    0x00429E3E: ("mov", "ecx,0x6", "copy six CharacterData words"),
    0x00429E43: ("rep", "movs DWORD PTR es:[edi],DWORD PTR ds:[esi]", "copy CharacterData record"),
    0x00429E45: ("fld", "DWORD PTR ds:0x46a44c", "load exact sqrt input 2"),
    0x00429E51: ("call", "0x45bc34", "compute sqrt for diagonal speed"),
    0x00429E62: ("fdivr", "DWORD PTR [edx+0x9f4]", "divide orthogonal speed by sqrt 2"),
    0x00429E6B: ("fstp", "DWORD PTR [eax+0x9fc]", "store diagonal movement speed"),
    0x00429E71: ("fld", "DWORD PTR ds:0x46a44c", "reload exact sqrt input 2"),
    0x00429E7D: ("call", "0x45bc34", "compute sqrt for focused diagonal speed"),
    0x00429E8E: ("fdivr", "DWORD PTR [ecx+0x9f8]", "divide focused speed by sqrt 2"),
    0x00429E97: ("fstp", "DWORD PTR [edx+0xa00]", "store focused diagonal speed"),
    0x0042A082: ("mov", "DWORD PTR [ecx+0x9d4],0x3f800000", "store initial vertical multiplier 1"),
    # Replay registration freezes the configured multiplier to one.
    0x0042A266: ("mov", "DWORD PTR ds:0x6c6ec4,0x3f800000", "set replay framerate multiplier 1"),
    # The target sqrt wrapper reaches an x87 fsqrt for positive input.
    0x0045BC34: ("lea", "edx,[esp+0x4]", "locate sqrt argument"),
    0x0045BC38: ("call", "0x4603b5", "load and classify sqrt argument"),
    0x0045BC3E: ("fstcw", "WORD PTR [esp]", "capture x87 control word"),
    0x0045BC48: ("cmp", "WORD PTR [esp],0x27f", "check target control profile"),
    0x0045BC5C: ("fsqrt", "", "square root positive finite input"),
}

REQUIRED_COMPARISONS = {
    "0x00427e66": ("fnstsw ax; test ah,0x5; jp", "ZkTH06.X87Compare.test_5_jp_table", "lower player-y clamp"),
    "0x00427e99": ("fnstsw ax; test ah,0x5; jp", "ZkTH06.X87Compare.test_5_jp_table", "upper player-y clamp"),
    "0x00427159": ("fnstsw ax; and eax,0x4100; je", "ZkTH06.X87Compare.and_4100_je_table", "grab-top/item-bottom separation"),
    "0x00427171": ("fnstsw ax; test ah,0x5; jp", "ZkTH06.X87Compare.test_5_jp_table", "grab-bottom/item-top non-separation"),
}


def load_sealed(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"base ledger has an invalid artifact digest: {path}")
    return document


def pinned_blob(source_root: Path, source_file: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(source_root), "show", f"{UPSTREAM_REVISION}:{source_file}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ValueError(
            f"cannot read {source_file} at {UPSTREAM_REVISION}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def verify_sources(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blobs: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for source_file, line, anchor, role in SOURCE_ANCHORS:
        if source_file not in blobs:
            blobs[source_file] = pinned_blob(source_root, source_file)
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
    for name, expected in MAPPED_FUNCTIONS.items():
        function = by_name.get(name)
        if function is None or (function.start, function.size) != expected:
            got = None if function is None else (function.start, function.size)
            raise ValueError(f"mapping mismatch for {name}: expected {expected}, got {got}")
        rows.append({"name": name, "start": f"0x{function.start:08x}", "size": function.size})
    return rows


def verify_instructions(disassembly: str) -> list[dict[str, str]]:
    instructions = {
        instruction.address: instruction
        for instruction in x87_audit.parse_disassembly(disassembly)
    }
    rows: list[dict[str, str]] = []
    for address, (mnemonic, operands, role) in EXPECTED_INSTRUCTIONS.items():
        instruction = instructions.get(address)
        if instruction is None:
            raise ValueError(f"missing player-position instruction at 0x{address:08x}")
        if (instruction.mnemonic, instruction.operands) != (mnemonic, operands):
            raise ValueError(
                f"instruction mismatch at 0x{address:08x}: got "
                f"{instruction.mnemonic} {instruction.operands!r}, expected "
                f"{mnemonic} {operands!r}"
            )
        rows.append({"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role})
    return rows


def verify_constants(image: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for address, (expected_bits, value, role) in BINARY32_CONSTANTS.items():
        raw = run_ftol2_probe.extract_pe_range(image, address, 4)
        (actual_bits,) = struct.unpack("<I", raw)
        if actual_bits != expected_bits:
            raise ValueError(
                f"binary32 constant mismatch at 0x{address:08x}: "
                f"0x{actual_bits:08x} != 0x{expected_bits:08x}"
            )
        rows.append(
            {
                "address": f"0x{address:08x}",
                "bits": f"0x{actual_bits:08x}",
                "exact_value": value,
                "role": role,
            }
        )
    return rows


def verify_character_speeds(image: bytes) -> list[dict[str, Any]]:
    names = ["reimu-a", "reimu-b", "marisa-a", "marisa-b"]
    rows: list[dict[str, Any]] = []
    for index, expected in enumerate(EXPECTED_CHARACTER_SPEEDS):
        address = CHARACTER_SPEED_TABLE + index * CHARACTER_SPEED_RECORD_SIZE
        raw = run_ftol2_probe.extract_pe_range(image, address, 16)
        actual = list(struct.unpack("<4I", raw))
        if actual != expected:
            raise ValueError(f"character speed record mismatch at 0x{address:08x}")
        rows.append(
            {
                "name": names[index],
                "address": f"0x{address:08x}",
                "binary32_bits": [f"0x{bits:08x}" for bits in actual],
                "source_values": ["4", "2", "4", "2"]
                if index < 2
                else ["5", "2.5", "5", "2.5"],
            }
        )
    return rows


def verify_comparisons(base_ledger: dict[str, Any]) -> list[dict[str, str]]:
    if not any(
        row.get("id") == "x87-fcomp-status-branch-v1"
        for row in base_ledger.get("obligation_classes", [])
    ):
        raise ValueError("base ledger has no comparison obligation class")
    by_address = {
        row["address"]: row
        for row in base_ledger.get("sites", {}).get("comparisons", [])
        if row.get("class") == "x87-fcomp-status-branch-v1"
    }
    rows: list[dict[str, str]] = []
    for address, (signature, theorem, role) in REQUIRED_COMPARISONS.items():
        site = by_address.get(address)
        if site is None or site.get("consumer_signature") != signature:
            raise ValueError(f"base comparison mismatch at {address}")
        rows.append(
            {
                "address": address,
                "base_obligation_id": site["id"],
                "consumer_signature": signature,
                "truth_table_theorem": theorem,
                "role": role,
                "base_slice_disposition": site["slice_disposition"],
            }
        )
    return rows


def build_document(
    executable: Path,
    mapping_path: Path,
    base_ledger: dict[str, Any],
    source_root: Path,
    objdump: str,
    tool_path: Path,
) -> dict[str, Any]:
    image = executable.read_bytes()
    executable_hash = run_ftol2_probe.sha256(image)
    mapping_hash = x87_audit.sha256_file(mapping_path)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable hash does not match the pinned Japanese v1.02h image")
    if mapping_hash != arithmetic_obligations.PINNED_MAPPING_SHA256:
        raise ValueError("mapping hash does not match the pinned authoritative mapping")
    target = base_ledger.get("target", {})
    if target.get("executable_sha256") != executable_hash:
        raise ValueError("base ledger is bound to a different executable")
    if target.get("mapping_sha256") != mapping_hash:
        raise ValueError("base ledger is bound to a different mapping")

    source_anchors, source_hashes = verify_sources(source_root)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instructions(disassembly)

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "base_ledger_artifact_sha256": base_ledger["artifact_sha256"],
        },
        "generator": {
            "path": "tools/player_position_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
            "x87_audit_sha256": arithmetic_obligations.sha256_file(
                tool_path.parent / "x87_audit.py"
            ),
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
        "binary32_constants": verify_constants(image),
        "character_speed_table": verify_character_speeds(image),
        "checked_instruction_roles": instruction_rows,
        "comparison_contracts": verify_comparisons(base_ledger),
        "derived_contract": {
            "initial_and_respawn_y": "384",
            "movement_lower_y": "16",
            "movement_upper_y": "432",
            "grab_radius_y": "12",
            "grab_top_range_if_center_bounded": "4..420",
            "grab_bottom_range_if_center_bounded": "28..444",
            "ordered_clamp_exception_behavior": {
                "negative_infinity": "assign lower 16",
                "positive_infinity": "assign upper 432",
                "nan": "both JP branches skip assignment; NaN survives",
            },
            "lean_contracts": {
                "total_clamp": "ZkTH06.PlayerPosition.clamp_bounded_of_not_nan",
                "finite_movement_step": "ZkTH06.PlayerPosition.movement_step_y_bounded",
                "initial": "ZkTH06.PlayerPosition.initial_y_bounded",
                "respawn": "ZkTH06.PlayerPosition.respawn_y_bounded",
                "grab_box": "ZkTH06.PlayerPosition.bounded_center_grab_box",
            },
        },
        "evidence_status": (
            "exact static signatures, pinned source candidates, and proved model consequences; "
            "not verified decoding, compiler correspondence, whole-program write completeness, "
            "x87/binary32 semantics, invariant preservation, scheduling, or guest refinement"
        ),
        "open_obligations": [
            "Prove or translation-validate every checked instruction and source alignment.",
            "Prove the movement-area constants remain initialized across GameManager reinitialization.",
            "Prove all reachable speed, bomb-multiplier, and effective-rate writers are covered.",
            "Prove finite movement operands and the positive sqrt(2) path cannot produce a NaN candidate.",
            "Bind binary32 stores and the four ordered comparisons to the total Lean clamp/collision models.",
            "Prove Player update precedes item collision whenever collision can accept the player state.",
            "Prove no unmodeled direct or aliased writer corrupts player center/grab-box fields.",
            "Prove the zkVM guest refines the address-bound player-position and collision contract.",
        ],
        "counts": {
            "mapped_functions": len(MAPPED_FUNCTIONS),
            "source_anchors": len(source_anchors),
            "binary32_constants": len(BINARY32_CONSTANTS),
            "character_speed_records": len(EXPECTED_CHARACTER_SPEEDS),
            "checked_instruction_roles": len(instruction_rows),
            "comparison_contracts": len(REQUIRED_COMPARISONS),
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--mapping", type=Path, default=Path("repos/th06/config/mapping.csv"))
    parser.add_argument("--ledger", type=Path, default=Path("arithmetic/obligations-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    document = build_document(
        args.executable,
        args.mapping,
        load_sealed(args.ledger),
        args.source_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale player-position audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current player-position audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit the pinned Reimu-A Player::SpawnBullets allocation/geometry path."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import player_position_audit
import player_shooting_audit
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.player-bullet-spawn-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION

MAPPED_FUNCTIONS = {
    "th06::Player::FireBulletReimuA": (0x004260D0, 0x22),
    "th06::Player::FireSingleBullet": (0x00426100, 0x31B),
    "th06::Player::SpawnBullets": (0x00429820, 0x10E),
}

SOURCE_ANCHORS = [
    ("src/Player.cpp", 1043, "Player::SpawnBullets", "slot allocator entry"),
    ("src/Player.cpp", 1053, "curBulletIdx <", "80-slot scan"),
    ("src/Player.cpp", 1055, "bulletState !=", "skip non-unused slot"),
    ("src/Player.cpp", 1060, "if (!p->isFocus)", "callback selection"),
    ("src/Player.cpp", 1068, "bulletResult >= 0", "successful callback result"),
    ("src/Player.cpp", 1073, "bulletState =", "mark slot fired"),
    ("src/Player.cpp", 1083, "idx++", "advance bullet-data index"),
    ("src/Player.cpp", 1092, "FireSingleBullet", "shared callback"),
    ("src/Player.cpp", 1101, "currentPower >=", "power rank selection"),
    ("src/Player.cpp", 1106, "powerData->bullets + bulletIdx", "row selection"),
    ("src/Player.cpp", 1122, "framesSinceLastBullet %", "non-laser timer gate"),
    ("src/Player.cpp", 1126, "SetAndExecuteScriptIdx", "ANM boundary"),
    ("src/Player.cpp", 1127, "spawnPositionIdx", "player/orb source selector"),
    ("src/Player.cpp", 1135, "motion.x", "x motion add"),
    ("src/Player.cpp", 1136, "motion.y", "y motion add"),
    ("src/Player.cpp", 1138, "position.z =", "fixed z"),
    ("src/Player.cpp", 1140, "size.x", "size initialization"),
    ("src/Player.cpp", 1143, "unk_134.z", "direction initialization"),
    ("src/Player.cpp", 1144, "unk_134.y", "speed initialization"),
    ("src/Player.cpp", 1146, "cosf", "x velocity helper"),
    ("src/Player.cpp", 1148, "sinf", "y velocity helper"),
    ("src/Player.cpp", 1150, "InitializeForPopup", "age timer initialization"),
    ("src/Player.cpp", 1152, "bulletType", "type initialization"),
    ("src/Player.cpp", 1153, "damage", "damage initialization"),
    ("src/Player.cpp", 1175, "g_CharacterPowerDataReimuA", "fixed Reimu-A table"),
    ("src/BulletData.cpp", 11, "ReimuARank1", "rank-1 table"),
    ("src/BulletData.cpp", 16, "ReimuARank2", "rank-2 table"),
    ("src/BulletData.cpp", 25, "ReimuARank3", "rank-3 table"),
    ("src/BulletData.cpp", 134, "{1, 8", "rank-1 upper threshold"),
    ("src/BulletData.cpp", 135, "{3, 16", "rank-2 upper threshold"),
    ("src/BulletData.cpp", 136, "{4, 32", "rank-3 upper threshold"),
]

EXPECTED_INSTRUCTIONS = {
    # Reimu-A wrapper fixes the selected power table.
    0x004260D3: ("push", "0x476f78", "push fixed Reimu-A power table"),
    0x004260E8: ("call", "0x426100", "call FireSingleBullet"),
    # Power-rank and row selection.
    0x00426108: ("mov", "ax,ds:0x69d4b0", "load currentPower"),
    0x00426111: ("cmp", "eax,DWORD PTR [ecx+0x4]", "compare rank threshold"),
    0x00426119: ("add", "edx,0xc", "advance power rank"),
    0x00426124: ("imul", "eax,eax,0x24", "scale bullet-data index"),
    0x0042612A: ("add", "eax,DWORD PTR [ecx+0x8]", "select bullet-data row"),
    # Selected profile excludes the laser branch and uses integer remainder.
    0x00426135: ("mov", "al,BYTE PTR [edx+0x1f]", "load bullet type"),
    0x00426138: ("cmp", "eax,0x3", "test laser type"),
    0x004261E4: ("movsx", "ecx,WORD PTR [edx]", "load wait period"),
    0x004261EB: ("idiv", "ecx", "timer remainder"),
    0x004261F0: ("movsx", "ecx,WORD PTR [eax+0x2]", "load scheduled frame"),
    0x004261F4: ("cmp", "edx,ecx", "test timer gate"),
    # ANM request followed by source-position selection and geometry stores.
    0x00426216: ("mov", "WORD PTR [edx+0xb4],ax", "store requested ANM index"),
    0x00426232: ("call", "0x432430", "enter ANM execution boundary"),
    0x0042623C: ("mov", "al,BYTE PTR [edx+0x1e]", "load source position index"),
    0x0042624C: ("mov", "edx,DWORD PTR [ebp+0xc]", "select player position destination"),
    0x00426272: ("imul", "eax,eax,0xc", "scale orb index"),
    0x004262A8: ("fld", "DWORD PTR [ecx]", "load source x"),
    0x004262AA: ("fadd", "DWORD PTR [edx+0x4]", "add motion x"),
    0x004262B0: ("fstp", "DWORD PTR [eax]", "store rounded x"),
    0x004262C4: ("fld", "DWORD PTR [edx]", "load source y"),
    0x004262C6: ("fadd", "DWORD PTR [eax+0x8]", "add motion y"),
    0x004262CC: ("fstp", "DWORD PTR [ecx]", "store rounded y"),
    0x004262D1: ("mov", "DWORD PTR [edx+0x118],0x3efd70a4", "store position z 0.495"),
    0x004262E4: ("mov", "DWORD PTR [eax+0x11c],edx", "store size x"),
    0x004262F3: ("mov", "DWORD PTR [eax+0x120],edx", "store size y"),
    0x004262FC: ("mov", "DWORD PTR [eax+0x124],0x3f800000", "store size z 1"),
    0x0042630F: ("mov", "DWORD PTR [ecx+0x13c],eax", "store direction"),
    0x0042631E: ("mov", "DWORD PTR [ecx+0x138],eax", "store scalar speed"),
    0x00426336: ("call", "0x45bda4", "call cosine helper"),
    0x0042634D: ("fstp", "DWORD PTR [ecx+0x128]", "store velocity x"),
    0x00426365: ("call", "0x45bcf4", "call sine helper"),
    0x0042637C: ("fstp", "DWORD PTR [edx+0x12c]", "store velocity y"),
    0x00426390: ("mov", "DWORD PTR [ecx+0x8],0x0", "initialize age current"),
    0x0042639A: ("mov", "DWORD PTR [edx+0x4],0x0", "initialize age subframe"),
    0x004263A4: ("mov", "DWORD PTR [eax],0xfffffc19", "initialize age previous"),
    0x004263B5: ("mov", "WORD PTR [eax+0x150],dx", "store bullet type"),
    0x004263C6: ("mov", "WORD PTR [ecx+0x14c],ax", "store damage"),
    0x004263F6: ("cmp", "DWORD PTR [ebp+0x10],eax", "test final row after spawn"),
    0x00426408: ("cmp", "DWORD PTR [ebp+0x10],eax", "test final row after skip"),
    # Slot scan and callback result machine.
    0x00429830: ("add", "eax,0xa28", "address first Player bullet slot"),
    0x0042984D: ("add", "edx,0x158", "advance Player bullet slot"),
    0x00429856: ("cmp", "DWORD PTR [ebp-0x8],0x50", "bound scan to 80 slots"),
    0x00429863: ("movsx", "ecx,WORD PTR [eax+0x14e]", "load slot state"),
    0x0042986A: ("test", "ecx,ecx", "select unused state zero"),
    0x00429891: ("call", "DWORD PTR [edx+0x75c0]", "call unfocused callback"),
    0x004298B2: ("call", "DWORD PTR [ecx+0x75c4]", "call focused callback"),
    0x004298BE: ("cmp", "DWORD PTR [ebp-0x10],0x0", "test successful callback"),
    0x004298D0: ("mov", "DWORD PTR [edx+0x90],ecx", "copy bullet x to sprite x"),
    0x004298E2: ("mov", "DWORD PTR [edx+0x94],ecx", "copy bullet y to sprite y"),
    0x004298EB: ("mov", "DWORD PTR [edx+0x98],0x3efd70a4", "store sprite z 0.495"),
    0x004298F8: ("mov", "WORD PTR [eax+0x14e],0x1", "mark slot fired"),
    0x00429901: ("cmp", "DWORD PTR [ebp-0x10],0xfffffffe", "test stop result"),
    0x00429914: ("add", "ecx,0x1", "advance bullet-data index"),
    0x0042991A: ("cmp", "DWORD PTR [ebp-0x10],0xffffffff", "test retry same slot"),
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
            raise ValueError(f"missing bullet-spawn instruction at 0x{address:08x}")
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
    shooting: dict[str, Any],
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
    if shooting.get("kind") != player_shooting_audit.KIND:
        raise ValueError("selected shooting artifact has the wrong kind")
    if shooting.get("inputs", {}).get("executable_sha256") != executable_hash:
        raise ValueError("shooting artifact is bound to a different executable")

    source_anchors, source_hashes = verify_sources(source_root)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instructions(disassembly)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "player_shooting_artifact_sha256": shooting["artifact_sha256"],
        },
        "generator": {
            "path": "tools/player_bullets_audit.py",
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
            "route": "Reimu A",
            "supported_power": {"minimum": 0, "maximum": 31, "ranks": [1, 2, 3]},
            "slot_count": 80,
            "slot_stride": 344,
            "unused_state": 0,
            "fired_state": 1,
            "timer_domain": {"minimum": 0, "maximum": 29},
            "rank_thresholds": [8, 16, 32],
            "nonlaser_carried_fields": ["sidewaysMotion", "unk_134.x", "unk_152", "spawnPositionIdx"],
            "trigonometry_boundary": (
                "cosine/sine helper results are observed as fixed raw bits for the five directions; "
                "no host libm equivalence is claimed"
            ),
            "anm_boundary": "the transition emits the requested script index; SetAndExecuteScript remains external",
            "refinement_boundary": (
                "one local SpawnBullets call from pre-slot state to allocation and initialized geometry; "
                "no cross-call linkage, bullet update, collision, or ANM termination"
            ),
        },
        "evidence_status": (
            "exact static signatures and pinned source candidates for Reimu-A ranks 1-3 allocation and "
            "geometry, bound to the shooting-cadence audit; not verified decoding, compiler correspondence, "
            "reachability, trigonometric helper equivalence, ANM semantics, or guest refinement"
        ),
        "open_obligations": [
            "Translation-validate the checked instruction/source alignment.",
            "Prove the fixed trigonometric raw-bit table against the pinned helper implementation.",
            "Refine the requested ANM script into the complete future-live AnmVm state.",
            "Link separate spawn calls through bullet update, collision, and slot reclamation.",
            "Extend the power table beyond ranks 1-3 and then to the other shot routes.",
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
    parser.add_argument("--shooting", type=Path, default=Path("arithmetic/player-shooting-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    document = build_document(
        args.executable,
        args.mapping,
        load_sealed(args.shooting),
        args.source_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale player-bullet spawn audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current player-bullet spawn audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit the pinned Player-bullet update/order/writer boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import player_bullets_audit
import player_position_audit
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.player-bullet-lifecycle-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION

MAPPED_FUNCTIONS = {
    "th06::GameManager::IsInBounds": (0x0041B5E1, 0x82),
    "th06::Player::CalcDamageToEnemy": (0x004264B0, 0x77D),
    "th06::Player::OnUpdate": (0x004288C0, 0x8EA),
    "th06::Player::UpdatePlayerBullets": (0x004291B0, 0x55B),
    "th06::Player::SpawnBullets": (0x00429820, 0x10E),
    "th06::Player::DrawBulletExplosions": (0x00429BB0, 0x99),
    "th06::Player::AddedCallback": (0x00429C50, 0x45E),
    "th06::AnmManager::ExecuteScript": (0x00433960, 0x1103),
}

SOURCE_ANCHORS = [
    ("src/Player.cpp", 124, "for (curBullet", "registration clears all 80 slots"),
    ("src/Player.cpp", 126, "bulletState = 0", "registration writes unused state"),
    ("src/Player.cpp", 325, "HandlePlayerInputs", "movement precedes bullet update"),
    ("src/Player.cpp", 328, "UpdatePlayerBullets", "bullet update call"),
    ("src/Player.cpp", 334, "lastEnemyHit.x = -999.0", "target reset after bullet update"),
    ("src/Player.cpp", 338, "UpdateFireBulletsTimer", "spawn cadence follows bullet update"),
    ("src/Player.cpp", 420, "bulletState ==", "collision accepts fired bullet"),
    ("src/Player.cpp", 422, "anmFileIndex + 0x20", "collision ANM selection"),
    ("src/Player.cpp", 424, "position.z = 0.1", "collision gameplay z"),
    ("src/Player.cpp", 426, "bulletState =", "Enemy collision state writer"),
    ("src/Player.cpp", 427, "velocity.x /= 8.0f", "collision x slowdown"),
    ("src/Player.cpp", 428, "velocity.y /= 8.0f", "collision y slowdown"),
    ("src/Player.cpp", 487, "ARRAY_SIZE_SIGNED(player->bullets)", "80-slot update loop"),
    ("src/Player.cpp", 489, "bulletState ==", "unused slot skip"),
    ("src/Player.cpp", 571, "sprite.pos.x", "move x and overwrite sprite x"),
    ("src/Player.cpp", 573, "sprite.pos.y", "move y and overwrite sprite y"),
    ("src/Player.cpp", 575, "sprite.pos.z", "overwrite draw-only sprite z"),
    ("src/Player.cpp", 577, "IsInBounds", "loaded-sprite bounds call"),
    ("src/Player.cpp", 580, "bulletState =", "bounds reclamation"),
    ("src/Player.cpp", 583, "ExecuteScript", "ANM transition"),
    ("src/Player.cpp", 585, "bulletState =", "ANM reclamation"),
    ("src/Player.cpp", 587, "unk_140.Tick", "bullet age tick"),
    ("src/Player.cpp", 966, "bulletState !=", "draw collision-state gate"),
    ("src/Player.cpp", 974, "sprite.pos.z = 0.4f", "draw-only z writer"),
    ("src/Player.cpp", 1073, "bulletState =", "spawn fired-state writer"),
    ("src/GameManager.cpp", 96, "width / 2.0f + x", "left bounds predicate"),
    ("src/GameManager.cpp", 100, "x - width / 2.0f", "right bounds predicate"),
    ("src/GameManager.cpp", 104, "height / 2.0f + y", "top bounds predicate"),
    ("src/GameManager.cpp", 108, "y - height / 2.0f", "bottom bounds predicate"),
    ("src/AnmManager.cpp", 1022, "AnmManager::ExecuteScript", "ANM interpreter entry"),
    ("src/AnmManager.cpp", 1366, "currentTimeInScript.Tick", "ANM timer tick"),
]

PLAYER_BULLET_STATE_WRITERS = [126, 426, 580, 585, 1073]

EXPECTED_INSTRUCTIONS = {
    0x00429127: ("call", "0x4291b0", "OnUpdate calls bullet update"),
    0x00429166: ("mov", "DWORD PTR [ebp-0x18],0xc479c000", "reset target x after update"),
    0x00429199: ("call", "0x429710", "shooting cadence follows target reset"),
    0x00429229: ("cmp", "DWORD PTR [ebp-0xc],0x50", "bound update loop to 80 slots"),
    0x00429236: ("movsx", "ecx,WORD PTR [eax+0x14e]", "load slot state"),
    0x00429246: ("movsx", "eax,WORD PTR [edx+0x150]", "load bullet type"),
    0x004295F4: ("fld", "DWORD PTR ds:0x6c6ec0", "load effective rate for x"),
    0x004295FA: ("fmul", "DWORD PTR [ecx+0x128]", "multiply x velocity"),
    0x00429603: ("fadd", "DWORD PTR [edx]", "add prior x"),
    0x00429608: ("fstp", "DWORD PTR [eax]", "store rounded gameplay x"),
    0x00429612: ("mov", "DWORD PTR [ecx+0x90],eax", "overwrite sprite x"),
    0x00429627: ("fld", "DWORD PTR ds:0x6c6ec0", "load effective rate for y"),
    0x0042962D: ("fmul", "DWORD PTR [edx+0x12c]", "multiply y velocity"),
    0x00429636: ("fadd", "DWORD PTR [eax]", "add prior y"),
    0x0042963B: ("fstp", "DWORD PTR [ecx]", "store rounded gameplay y"),
    0x00429645: ("mov", "DWORD PTR [edx+0x94],ecx", "overwrite sprite y"),
    0x00429657: ("mov", "DWORD PTR [edx+0x98],ecx", "overwrite sprite z"),
    0x00429675: ("mov", "eax,DWORD PTR [edx+0x2c]", "load sprite height"),
    0x00429682: ("mov", "eax,DWORD PTR [edx+0x30]", "load sprite width"),
    0x0042969F: ("call", "0x41b5e1", "call bounds predicate"),
    0x004296AB: ("mov", "WORD PTR [edx+0x14e],0x0", "bounds writes unused state"),
    0x004296BE: ("call", "0x433960", "execute bullet ANM"),
    0x004296CA: ("mov", "WORD PTR [ecx+0x14e],0x0", "ANM exit writes unused state"),
    0x004296FD: ("call", "0x424285", "tick bullet age timer"),
    0x00426848: ("mov", "WORD PTR [eax+0x14e],0x2", "Enemy hit writes collided state"),
    0x0042685A: ("fdiv", "DWORD PTR ds:0x46a2bc", "divide collision x velocity by eight"),
    0x00426872: ("fdiv", "DWORD PTR ds:0x46a2bc", "divide collision y velocity by eight"),
    0x00429BE8: ("movsx", "ecx,WORD PTR [eax+0x14e]", "draw loads collision state"),
    0x00429C2A: ("mov", "DWORD PTR [ecx+0x98],0x3ecccccd", "draw stores sprite z 0.4"),
}


def load_sealed(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"input artifact has an invalid digest: {path}")
    return document


def verify_sources(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blobs: dict[str, bytes] = {}
    anchors: list[dict[str, Any]] = []
    for source_file, line, anchor, role in SOURCE_ANCHORS:
        if source_file not in blobs:
            blobs[source_file] = player_position_audit.pinned_blob(source_root, source_file)
        lines = blobs[source_file].decode("utf-8").splitlines()
        if line <= 0 or line > len(lines) or anchor not in lines[line - 1]:
            raise ValueError(f"source anchor mismatch at {source_file}:{line}: {anchor!r}")
        anchors.append({"file": source_file, "line": line, "anchor": anchor, "role": role})

    player_lines = blobs["src/Player.cpp"].decode("utf-8").splitlines()
    assignment = re.compile(r"\bbulletState\s*=(?!=)")
    observed_writers = [
        number
        for number, line in enumerate(player_lines, 1)
        if assignment.search(line)
    ]
    if observed_writers != PLAYER_BULLET_STATE_WRITERS:
        raise ValueError(f"Player bullet-state writer set changed: {observed_writers}")
    return anchors, {
        name: hashlib.sha256(blob).hexdigest() for name, blob in sorted(blobs.items())
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
        if instruction is None or (instruction.mnemonic, instruction.operands) != (mnemonic, operands):
            got = None if instruction is None else (instruction.mnemonic, instruction.operands)
            raise ValueError(f"instruction mismatch at 0x{address:08x}: got {got}")
        rows.append({"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role})
    return rows


def build_document(
    executable: Path,
    mapping_path: Path,
    spawn: dict[str, Any],
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
    if spawn.get("kind") != player_bullets_audit.KIND:
        raise ValueError("selected spawn artifact has the wrong kind")
    if spawn.get("inputs", {}).get("executable_sha256") != executable_hash:
        raise ValueError("spawn artifact is bound to a different executable")
    source_anchors, source_hashes = verify_sources(source_root)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    instruction_rows = verify_instructions(disassembly)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "player_bullet_spawn_artifact_sha256": spawn["artifact_sha256"],
        },
        "generator": {
            "path": "tools/player_bullet_lifecycle_audit.py",
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
        "writer_inventory": {
            "player_bullet_state_source_lines": PLAYER_BULLET_STATE_WRITERS,
            "states": {"unused": 0, "fired": 1, "collided": 2},
            "owners": ["registration", "Enemy collision", "bounds", "ANM exit", "spawn"],
        },
        "derived_profile_contract": {
            "route": "Reimu A rank 1",
            "anchor_game_frame": 1,
            "maximum_collision_free_game_frame": 207,
            "first_external_collision_game_frame": 208,
            "power": 0,
            "effective_rate_bits": "0x3f800000",
            "straight_sprite_size_bits": ["0x41600000", "0x41600000"],
            "anm_script": 1088,
            "homing_target_noninterference": (
                "EnemyManager may write positionOfLastEnemyHit in the selected prefix, but the "
                "type-0 route bypasses the type-1-only target read"
            ),
            "draw_noninterference": (
                "DrawBulletExplosions may change collided sprite.pos.z after the post-calc anchor, "
                "but UpdatePlayerBullets overwrites x, y, and z before bounds or ExecuteScript"
            ),
            "refinement_boundary": (
                "fixed empty frame-1 pool through frame 207 using replay inputs only; Enemy collision, "
                "homing, item power, and collision ANM are excluded"
            ),
        },
        "evidence_status": (
            "pinned source, mapping, and instruction signatures for update order, bounds, timer, "
            "collision, draw-only z, and all lexical Player bullet-state writers; not verified decoding, "
            "compiler correspondence, complete alias analysis, ANM-data semantics, or guest refinement"
        ),
        "open_obligations": [
            "Translation-validate the checked instruction/source alignment.",
            "Bind script 1088 nontermination and 14-by-14 sprite selection directly to pinned ANM data.",
            "Prove complete alias-aware writer noninterference rather than the lexical source inventory.",
            "Compose Enemy/ECL state to derive collision and the last-enemy-hit homing target.",
            "Extend arithmetic refinement from the current finite normal PC24 profile.",
        ],
        "counts": {
            "mapped_functions": len(MAPPED_FUNCTIONS),
            "source_anchors": len(source_anchors),
            "checked_instruction_roles": len(instruction_rows),
            "player_bullet_state_writers": len(PLAYER_BULLET_STATE_WRITERS),
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--mapping", type=Path, default=Path("repos/th06/config/mapping.csv"))
    parser.add_argument("--spawn", type=Path, default=Path("arithmetic/player-bullets-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()
    document = build_document(
        args.executable,
        args.mapping,
        load_sealed(args.spawn),
        args.source_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale Player bullet-lifecycle audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current Player bullet-lifecycle audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

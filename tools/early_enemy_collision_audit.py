#!/usr/bin/env python3
"""Audit the pinned early Stage-1 Enemy-to-Player collision slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import player_bullet_lifecycle_audit
import player_position_audit
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.early-enemy-collision-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION
STAGE1_ECL_SHA256 = "9d9a40e9f7e3ab9346d3874438134659cacf9d34f4aff57b96b4be4ea85b99d7"

MAPPED_FUNCTIONS = {
    "th06::EclManager::RunEcl": (0x004074A0, 0x3504),
    "th06::EnemyManager::SpawnEnemy": (0x00411390, 0x122),
    "th06::EnemyManager::RunEclTimeline": (0x00411530, 0x833),
    "th06::EnemyManager::OnUpdate": (0x004123E0, 0xA5F),
    "th06::Enemy::Move": (0x00413380, 0xAA),
    "th06::GameManager::IsInBounds": (0x0041B5E1, 0x82),
    "th06::utils::AddNormalizeAngle": (0x0041E850, 0x7F),
    "th06::Player::CalcDamageToEnemy": (0x004264B0, 0x77D),
}

SOURCE_ANCHORS = [
    ("src/EnemyManager.cpp", 99, "ARRAY_SIZE_SIGNED(this->enemies) - 1", "lowest-free-slot spawn scan"),
    ("src/EnemyManager.cpp", 104, "*newEnemy = this->enemyTemplate", "fixed Enemy template copy"),
    ("src/EnemyManager.cpp", 109, "newEnemy->position = *pos", "timeline position initialization"),
    ("src/EnemyManager.cpp", 110, "CallEclSub", "Sub0 context initialization"),
    ("src/EnemyManager.cpp", 111, "RunEcl(newEnemy)", "time-zero ECL execution at spawn"),
    ("src/EnemyManager.cpp", 173, "while (0 <= this->timelineInstr->time)", "ordered timeline scan"),
    ("src/EnemyManager.cpp", 183, "this->SpawnEnemy", "opcode-0 deterministic spawn"),
    ("src/EnemyManager.cpp", 532, "RunEclTimeline", "timeline precedes Enemy loop"),
    ("src/EnemyManager.cpp", 541, "curEnemy->Move", "movement precedes ECL and collision"),
    ("src/EnemyManager.cpp", 543, "hasBeenInBounds == 0", "one-way in-bounds gate"),
    ("src/EnemyManager.cpp", 565, "RunEcl(curEnemy)", "ECL precedes Player damage call"),
    ("src/EnemyManager.cpp", 597, "CalcDamageToEnemy", "Enemy AABB Player-damage call"),
    ("src/EnemyManager.cpp", 602, "(damage / 5) * 10", "per-hit score update"),
    ("src/EnemyManager.cpp", 634, "curEnemy->life -= damage", "damageable life update"),
    ("src/EnemyManager.cpp", 636, "positionOfLastEnemyHit.y", "highest-y target selection"),
    ("src/EnemyManager.cpp", 641, "0 >= curEnemy->life", "death gate"),
    ("src/EnemyManager.cpp", 661, "AddScore(curEnemy->score)", "death score"),
    ("src/EnemyManager.cpp", 662, "isSlotOccupied = 0", "death removes Enemy slot"),
    ("src/EnemyManager.cpp", 740, "timelineTime.Tick", "timeline tick after Enemy loop"),
    ("src/EnemyManager.cpp", 867, "position.x +=", "non-inverted x move"),
    ("src/EnemyManager.cpp", 873, "position.y +=", "y move"),
    ("src/EclManager.cpp", 330, "ECL_OPCODE_MOVEVELOCITY", "Sub0 angle/speed opcode"),
    ("src/EclManager.cpp", 336, "ECL_OPCODE_MOVEANGULARVELOCITY", "Sub0 turn opcode"),
    ("src/EclManager.cpp", 668, "ECL_OPCODE_ENEMYSETHITBOX", "Sub0 hitbox opcode"),
    ("src/EclManager.cpp", 936, "AddNormalizeAngle", "movement-mode angle update"),
    ("src/EclManager.cpp", 939, "sincosmul", "axis-speed trigonometry"),
    ("src/Player.cpp", 356, "SetVecCorners", "Enemy AABB corners"),
    ("src/Player.cpp", 362, "ARRAY_SIZE_SIGNED(this->bullets)", "80-slot damage scan"),
    ("src/Player.cpp", 372, "bulletTopLeft.y", "AABB exclusion predicate"),
    ("src/Player.cpp", 380, "damage += bullet->damage", "non-bomb damage"),
    ("src/Player.cpp", 422, "anmFileIndex + 0x20", "collision ANM selection"),
    ("src/Player.cpp", 424, "position.z = 0.1", "collision gameplay z"),
    ("src/Player.cpp", 426, "PLAYER_BULLET_STATE_COLLIDED", "collision state"),
    ("src/Player.cpp", 427, "velocity.x /= 8.0f", "collision slowdown"),
]

EXPECTED_INSTRUCTIONS = {
    0x004123F0: ("call", "0x411530", "timeline before Enemy loop"),
    0x0041246A: ("call", "0x413380", "Enemy movement"),
    0x0041258A: ("call", "0x4074a0", "Enemy ECL execution"),
    0x004127D0: ("call", "0x4264b0", "Player damage call"),
    0x004127D8: ("cmp", "DWORD PTR [ebp-0x8],0x46", "damage cap at 70"),
    0x004127EE: ("idiv", "ecx", "damage score division by five"),
    0x004127F0: ("imul", "eax,eax,0xa", "damage score multiplication by ten"),
    0x004127F9: ("mov", "ds:0x69bca4,eax", "store score"),
    0x0041288D: ("sub", "edx,DWORD PTR [ebp-0x8]", "subtract Enemy life"),
    0x00412893: ("mov", "DWORD PTR [eax+0xce4],edx", "store Enemy life"),
    0x0041289C: ("fld", "DWORD PTR ds:0x6cb048", "load prior target y"),
    0x004128A2: ("fcomp", "DWORD PTR [ecx+0xc70]", "compare Enemy y"),
    0x004128D4: ("cmp", "DWORD PTR [eax+0xce4],0x0", "death check"),
    0x00412A2F: ("add", "edx,DWORD PTR [ebp-0x4c]", "add death score"),
    0x00412A41: ("and", "cl,0x7f", "clear active flag"),
    0x00412A47: ("mov", "BYTE PTR [edx+0xe50],cl", "store inactive flag"),
    0x00412E31: ("call", "0x424285", "tick timeline timer"),
    0x004133A3: ("fld", "DWORD PTR ds:0x6c6ec0", "load effective rate for x"),
    0x004133A9: ("fmul", "DWORD PTR [edx+0xc84]", "multiply x axis speed"),
    0x004133B2: ("fadd", "DWORD PTR [eax+0xc6c]", "add prior x"),
    0x004133BB: ("fstp", "DWORD PTR [ecx+0xc6c]", "round/store x"),
    0x004133E7: ("fld", "DWORD PTR ds:0x6c6ec0", "load effective rate for y"),
    0x004133ED: ("fmul", "DWORD PTR [edx+0xc88]", "multiply y axis speed"),
    0x004133F6: ("fadd", "DWORD PTR [eax+0xc70]", "add prior y"),
    0x004133FF: ("fstp", "DWORD PTR [ecx+0xc70]", "round/store y"),
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
    ecl: Path,
    mapping_path: Path,
    lifecycle: dict[str, Any],
    source_root: Path,
    objdump: str,
    tool_path: Path,
) -> dict[str, Any]:
    executable_hash = arithmetic_obligations.sha256_file(executable)
    ecl_hash = arithmetic_obligations.sha256_file(ecl)
    mapping_hash = arithmetic_obligations.sha256_file(mapping_path)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable does not match Japanese v1.02h")
    if ecl_hash != STAGE1_ECL_SHA256:
        raise ValueError("Stage-1 ECL does not match the selected data file")
    if mapping_hash != arithmetic_obligations.PINNED_MAPPING_SHA256:
        raise ValueError("mapping does not match the pinned authoritative mapping")
    if lifecycle.get("kind") != player_bullet_lifecycle_audit.KIND:
        raise ValueError("parent lifecycle artifact has the wrong kind")
    source_anchors, source_hashes = verify_sources(source_root)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "stage1_ecl_sha256": ecl_hash,
            "player_bullet_lifecycle_artifact_sha256": lifecycle["artifact_sha256"],
        },
        "generator": {
            "path": "tools/early_enemy_collision_audit.py",
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
        "checked_instruction_roles": verify_instructions(disassembly),
        "decoded_stage1_profile": {
            "timeline_times": [128, 144, 160, 176, 192],
            "post_calc_game_frames": [129, 145, 161, 177, 193],
            "sub_id": 0,
            "x_bits": ["0x42700000", "0x42880000", "0x42980000", "0x42a80000", "0x42b80000"],
            "y_bits": "0xc2000000",
            "life": [8, 32, 32, 32, 32],
            "score": 300,
            "hitbox_bits": ["0x41e00000", "0x41e00000", "0x42000000"],
            "anm_script": 769,
            "initial_angle_bits": "0x3fc90fdb",
            "speed_bits": "0x40000000",
            "turn_ecl_time": 40,
            "angular_velocity_bits": "0xbcc90fdb",
            "randomized_timeline_operands": False,
        },
        "derived_profile_contract": {
            "route": "Reimu A rank 1, Stage 1 Lunatic replay prefix",
            "anchor_game_frame": 1,
            "last_game_frame": 208,
            "first_damage_call_game_frame": 137,
            "first_collision_game_frame": 208,
            "collision_damage": 48,
            "collision_slot": 2,
            "post_collision_score": 390,
            "enemy_witnesses": "none; fixed timeline and prior Enemy state determine every call AABB",
            "trigonometry": (
                "40-entry axis-speed table indexed only by derived ECL time 41..80; both oracles "
                "match every reachable retained Enemy entry"
            ),
            "reordered_dead_state_noninterference": (
                "the killed slot's time-81 angle/axis update is omitted after its frame-208 position "
                "and collision are derived; the original immediately clears the slot and no selected "
                "consumer reads those dead fields"
            ),
            "omitted_ecl_shooting_noninterference": (
                "Sub0 bullet-shooting side effects are outside this projection; through frame 208 "
                "they do not write Enemy position, hitbox, life, Player bullets, target, or score"
            ),
        },
        "evidence_status": (
            "pinned ECL hash plus source, mapping, and instruction signatures for timeline, movement, "
            "ECL-before-collision ordering, damage, target, life, death, and score; finite dual-oracle "
            "raw-bit validation is stored separately"
        ),
        "open_obligations": [
            "Mechanically decode the selected ECL records from the pinned data hash.",
            "Prove the finite curved-axis table against x87 fsincos/sincosmul semantics.",
            "Translation-validate the checked instruction/source alignment.",
            "Prove alias-aware noninterference for omitted ECL shooting, effects, items, and ANM writes.",
            "Extend beyond the first collision by modeling collided-bullet ANM lifetime and later Enemy groups.",
        ],
        "counts": {
            "mapped_functions": len(MAPPED_FUNCTIONS),
            "source_anchors": len(SOURCE_ANCHORS),
            "checked_instruction_roles": len(EXPECTED_INSTRUCTIONS),
            "timeline_spawns": 5,
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--ecl", required=True, type=Path)
    parser.add_argument("--mapping", type=Path, default=Path("repos/th06/config/mapping.csv"))
    parser.add_argument("--lifecycle", type=Path, default=Path("arithmetic/player-bullet-lifecycle-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()
    document = build_document(
        args.executable,
        args.ecl,
        args.mapping,
        load_sealed(args.lifecycle),
        args.source_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale early Enemy-collision audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current early Enemy-collision audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

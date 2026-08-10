#!/usr/bin/env python3
"""Audit the finite-prefix obligations for the complete first Stage-1 wave."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import early_enemy_collision_audit
import player_bullet_lifecycle_audit
import player_position_audit


SCHEMA_VERSION = 1
KIND = "zkth06.first-wave-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION

SOURCE_ANCHORS = [
    ("src/Player.cpp", 487, "ARRAY_SIZE_SIGNED(player->bullets)", "complete 80-slot update scan"),
    ("src/Player.cpp", 571, "sprite.pos.x", "gameplay and sprite x movement"),
    ("src/Player.cpp", 573, "sprite.pos.y", "gameplay and sprite y movement"),
    ("src/Player.cpp", 575, "sprite.pos.z", "draw-only z overwrite"),
    ("src/Player.cpp", 577, "IsInBounds", "sprite-sized bounds test"),
    ("src/Player.cpp", 583, "ExecuteScript", "collision ANM execution"),
    ("src/Player.cpp", 587, "unk_140.Tick", "bullet age tick"),
    ("src/EnemyManager.cpp", 641, "0 >= curEnemy->life", "Enemy death gate"),
    ("src/EnemyManager.cpp", 661, "AddScore(curEnemy->score)", "fixed Enemy death score"),
    ("src/EnemyManager.cpp", 662, "isSlotOccupied = 0", "Enemy slot reclamation"),
    ("src/EnemyManager.cpp", 670, "itemDrop >= 0", "death-item writer branch"),
    ("src/EnemyManager.cpp", 673, "SpawnItem", "death item spawn"),
    ("src/EnemyManager.cpp", 675, "ITEM_RANDOM_ITEM", "random item branch"),
    ("src/ItemManager.cpp", 157, "CalcItemBoxCollision", "item-to-Player interaction gate"),
    ("src/ItemManager.cpp", 182, "currentPower++", "small-power item state write"),
    ("src/ItemManager.cpp", 189, "AddScore(10)", "first omitted retained-score writer"),
    ("src/AnmManager.cpp", 1366, "currentTimeInScript.Tick", "non-exiting ANM timer tick"),
]


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


def build_document(
    executable: Path,
    lifecycle: dict[str, Any],
    early: dict[str, Any],
    source_root: Path,
    tool_path: Path,
) -> dict[str, Any]:
    executable_hash = arithmetic_obligations.sha256_file(executable)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable does not match Japanese v1.02h")
    if lifecycle.get("kind") != player_bullet_lifecycle_audit.KIND:
        raise ValueError("parent lifecycle artifact has the wrong kind")
    if early.get("kind") != early_enemy_collision_audit.KIND:
        raise ValueError("parent early-gameplay artifact has the wrong kind")
    for parent in (lifecycle, early):
        if parent.get("inputs", {}).get("executable_sha256") != executable_hash:
            raise ValueError("parent artifact is bound to another executable")
    anchors, source_hashes = verify_sources(source_root)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "player_bullet_lifecycle_artifact_sha256": lifecycle["artifact_sha256"],
            "early_enemy_collision_artifact_sha256": early["artifact_sha256"],
            "stage1_ecl_sha256": early["inputs"]["stage1_ecl_sha256"],
        },
        "generator": {
            "path": "tools/first_wave_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
        },
        "upstream": {
            "url": UPSTREAM_URL,
            "revision": UPSTREAM_REVISION,
            "source_files": source_hashes,
            "anchors": anchors,
            "correspondence_status": "inherits pinned parent mapping/disassembly checks; source extension is manual",
        },
        "derived_profile_contract": {
            "route": "Reimu A rank 1, Stage 1 Lunatic replay prefix",
            "anchor_game_frame": 208,
            "last_game_frame": 229,
            "enemy_death_game_frames": [208, 213, 219, 224, 229],
            "collision_slots": [2, 3, 4, 0, 1],
            "damage_per_collision": 48,
            "post_wave_score": 1950,
            "post_wave_active_enemies": 0,
            "post_wave_collided_bullets": 5,
            "collision_anm": {
                "anm_file_index": 1120,
                "active_sprite_index": 1090,
                "size_bits": ["0x41800000", "0x41800000"],
                "maximum_timer_current": 22,
                "first_observed_exit_game_frame": 238,
            },
            "finite_prefix_noninterference": {
                "rng_and_effects": (
                    "death effects consume RNG generations 27..157 but do not write the retained "
                    "Player/bullet, Enemy, target, or score projection through frame 229"
                ),
                "items": (
                    "deaths spawn omitted item state; no item touches the retained projection through "
                    "frame 229, while the first observed feedback is the +10 power-item score/power "
                    "write at frame 249"
                ),
                "enemy_sub0_shooting": (
                    "omitted Enemy bullet creation has no retained projection writer through frame 229"
                ),
            },
        },
        "evidence_status": (
            "inherits executable/source/mapping/instruction signatures from both parent audits, adds "
            "source anchors for collided-bullet continuation and the item feedback boundary, and is "
            "paired with finite retail/reference raw-bit validation"
        ),
        "open_obligations": [
            "Decode and bind collision ANM 1120 directly from pinned player01.anm data.",
            "Prove alias-aware RNG/effect/item noninterference instead of relying on the finite boundary audit.",
            "Model spawned item state before extending the score-bearing kernel to frame 249.",
            "Refine the fixed x87 trigonometric table against fsincos semantics.",
            "Translation-validate the inherited source/disassembly correspondence.",
        ],
        "counts": {
            "source_anchors": len(anchors),
            "enemy_deaths": 5,
            "incremental_transitions": 21,
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--lifecycle", type=Path, default=Path("arithmetic/player-bullet-lifecycle-v1.json"))
    parser.add_argument("--early", type=Path, default=Path("arithmetic/early-enemy-collision-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()
    document = build_document(
        args.executable,
        load_sealed(args.lifecycle),
        load_sealed(args.early),
        args.source_root,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale first-wave audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current first-wave audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

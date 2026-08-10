#!/usr/bin/env python3
"""Audit the first death-Item spawn, motion, and collection profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import first_wave_audit
import item_score_audit
import player_position_audit


SCHEMA_VERSION = 1
KIND = "zkth06.first-item-audit"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = player_position_audit.UPSTREAM_REVISION

SOURCE_ANCHORS = [
    ("src/EnemyManager.cpp", 675, "ITEM_RANDOM_ITEM", "random-drop branch"),
    ("src/EnemyManager.cpp", 677, "randomItemSpawnIndex % 3", "random-drop cadence"),
    ("src/EnemyManager.cpp", 681, "SpawnItem", "random-table Item spawn"),
    ("src/EnemyManager.cpp", 683, "randomItemTableIndex++", "random-table cursor write"),
    ("src/EnemyManager.cpp", 689, "randomItemSpawnIndex++", "random-drop cursor write"),
    ("src/ItemManager.cpp", 29, "nextIndex++", "Item allocator cursor write"),
    ("src/ItemManager.cpp", 47, "isInUse = 1", "Item slot activation"),
    ("src/ItemManager.cpp", 48, "currentPosition", "death-position copy"),
    ("src/ItemManager.cpp", 50, "-2.2f", "initial vertical velocity"),
    ("src/ItemManager.cpp", 54, "InitializeForPopup", "Item timer initialization"),
    ("src/ItemManager.cpp", 102, "itemCount = 0", "per-frame active counter reset"),
    ("src/ItemManager.cpp", 141, "currentPosition +=", "Item motion update"),
    ("src/ItemManager.cpp", 150, "0.03f", "Item vertical acceleration"),
    ("src/ItemManager.cpp", 157, "CalcItemBoxCollision", "Player collection gate"),
    ("src/ItemManager.cpp", 182, "currentPower++", "small-power retained write"),
    ("src/ItemManager.cpp", 189, "AddScore(10)", "small-power score write"),
    ("src/ItemManager.cpp", 205, "IncreaseSubrank(1)", "small-power subrank write"),
    ("src/Player.cpp", 583, "ExecuteScript", "Player-bullet collision ANM exit"),
    ("src/Player.cpp", 585, "PLAYER_BULLET_STATE_UNUSED", "collision slot reclamation"),
    ("src/Player.cpp", 1355, "PLAYER_STATE_ALIVE", "collection life-state gate"),
    ("src/Player.cpp", 1364, "grabItemTopLeft.x", "ordered Item AABB comparisons"),
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
    first_wave: dict[str, Any],
    item_score: dict[str, Any],
    source_root: Path,
    tool_path: Path,
) -> dict[str, Any]:
    executable_hash = arithmetic_obligations.sha256_file(executable)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable does not match Japanese v1.02h")
    if first_wave.get("kind") != first_wave_audit.KIND:
        raise ValueError("first-wave parent has the wrong kind")
    if item_score.get("kind") != item_score_audit.KIND:
        raise ValueError("item-score parent has the wrong kind")
    for parent in (first_wave, item_score):
        if parent.get("inputs", {}).get("executable_sha256") != executable_hash:
            raise ValueError("parent artifact is bound to another executable")
    anchors, source_hashes = verify_sources(source_root)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "first_wave_artifact_sha256": first_wave["artifact_sha256"],
            "item_score_artifact_sha256": item_score["artifact_sha256"],
            "stage1_ecl_sha256": first_wave["inputs"]["stage1_ecl_sha256"],
        },
        "generator": {
            "path": "tools/first_item_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
        },
        "upstream": {
            "url": UPSTREAM_URL,
            "revision": UPSTREAM_REVISION,
            "source_files": source_hashes,
            "anchors": anchors,
            "correspondence_status": (
                "inherits the pinned first-wave and Item-score audits; the added source "
                "anchors remain a manual source-level correspondence layer"
            ),
        },
        "derived_profile_contract": {
            "route": "Reimu A, difficulty 1 (Normal), Stage 1 replay prefix",
            "anchor_game_frame": 208,
            "last_game_frame": 249,
            "random_item_spawn_index_at_anchor": 2,
            "enemy_death_game_frames_after_anchor": [213, 219, 224, 229],
            "spawn": {
                "game_frame": 219,
                "slot": 0,
                "item_type": "ITEM_POWER_SMALL",
                "random_item_table_index_before": 0,
                "initial_velocity_y_bits": "0xc00ccccd",
                "acceleration_y_bits": "0x3cf5c28f",
            },
            "collection": {
                "game_frame": 249,
                "score_before": 1950,
                "score_after": 1960,
                "power_before": 0,
                "power_after": 1,
                "subrank_before": 0,
                "subrank_after": 1,
            },
            "collision_anm_reclamation_frames": [238, 243, 249],
            "finite_prefix_noninterference": {
                "effects_and_sound": (
                    "death particles, popups, and sound do not feed the retained Player, bullet, "
                    "Item, Enemy, score, power, subrank, or allocator projection through frame 249"
                ),
                "enemy_bullets": (
                    "Sub0 shooting remains outside the retained projection and has no Player hit, "
                    "graze, or Item writer on this finite prefix"
                ),
                "item_anm": (
                    "the Item sprite script has no retained gameplay writer before collection; "
                    "Item timer and gameplay geometry are modeled directly"
                ),
            },
        },
        "evidence_status": (
            "paired with 300-frame retail/reference raw-bit Item differential evidence and a "
            "frame-by-frame state vector through the first collection"
        ),
        "open_obligations": [
            "Translation-validate the added Item and collision-ANM source correspondence against the executable.",
            "Decode and bind the relevant Item and collision ANM scripts directly from pinned data.",
            "Replace finite-prefix enemy-bullet/effect noninterference with an alias-aware proof.",
            "Compose the second Enemy wave, RNG state, ECL contexts, and Enemy bullets before stepping past frame 249.",
        ],
        "counts": {
            "source_anchors": len(anchors),
            "incremental_transitions": 41,
            "spawned_items": 1,
            "collected_items": 1,
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--first-wave", type=Path, default=Path("arithmetic/first-wave-v1.json"))
    parser.add_argument("--item-score", type=Path, default=Path("arithmetic/item-score-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()
    document = build_document(
        args.executable,
        load_sealed(args.first_wave),
        load_sealed(args.item_score),
        args.source_root,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != output:
            print(f"stale first-Item audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current first-Item audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Seal the Stage-1 second-wave Enemy/ECL/RNG/empty-bullet contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import arithmetic_obligations
import first_item_audit
import player_position_audit


SCHEMA_VERSION = 1
KIND = "zkth06.second-wave-audit"
SOURCE_ANCHORS = [
    ("src/EnemyManager.cpp", 92, "SpawnEnemy", "timeline Enemy allocator"),
    ("src/EnemyManager.cpp", 110, "CallEclSub", "initial ECL context"),
    ("src/EnemyManager.cpp", 111, "RunEcl", "spawn-time ECL execution"),
    ("src/EnemyManager.cpp", 532, "RunEclTimeline", "timeline-before-Enemy order"),
    ("src/EnemyManager.cpp", 541, "curEnemy->Move", "movement-before-ECL order"),
    ("src/EnemyManager.cpp", 565, "RunEcl(curEnemy)", "per-frame ECL execution"),
    ("src/EnemyManager.cpp", 597, "CalcDamageToEnemy", "Player-bullet collision writer"),
    ("src/EnemyManager.cpp", 677, "randomItemSpawnIndex % 3", "random-drop cadence"),
    ("src/EnemyManager.cpp", 699, "SpawnParticles", "common death effect"),
    ("src/EffectManager.cpp", 55, "GetRandomF32ZeroToOne", "splash x RNG"),
    ("src/EffectManager.cpp", 56, "GetRandomF32ZeroToOne", "splash y RNG"),
    ("src/EffectManager.cpp", 225, "SetAndExecuteScriptIdx", "effect ANM random-sprite path"),
    ("src/EffectManager.cpp", 250, "EffectManager::OnUpdate", "same-frame effect update"),
    ("src/Rng.cpp", 7, "GetRandomU16", "retained RNG transition"),
    ("src/Rng.cpp", 18, "GetRandomU16", "U32 consumes two U16 values"),
    ("src/BulletManager.cpp", 652, "BulletManager::OnUpdate", "Enemy-bullet manager transition"),
    ("src/BulletManager.cpp", 674, "bulletCount = 0", "active-pool count reset"),
    ("src/BulletManager.cpp", 1102, "time.Tick", "Enemy-bullet manager timer"),
    ("src/EclManager.cpp", 409, "SpawnBulletPattern", "ECL direct-shot sink"),
    ("src/EclManager.cpp", 449, "SpawnBulletPattern", "ECL shoot-now sink"),
    ("src/EclManager.cpp", 986, "SpawnBulletPattern", "interval-shot sink"),
]


def load_sealed(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"invalid parent digest: {path}")
    return document


def verify_sources(root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blobs: dict[str, bytes] = {}
    anchors: list[dict[str, Any]] = []
    for source_file, line, needle, role in SOURCE_ANCHORS:
        if source_file not in blobs:
            blobs[source_file] = player_position_audit.pinned_blob(root, source_file)
        lines = blobs[source_file].decode("utf-8").splitlines()
        if line > len(lines) or needle not in lines[line - 1]:
            raise ValueError(f"source anchor mismatch at {source_file}:{line}: {needle}")
        anchors.append({"file": source_file, "line": line, "anchor": needle, "role": role})
    return anchors, {name: hashlib.sha256(blob).hexdigest() for name, blob in sorted(blobs.items())}


def build(executable: Path, parent: dict[str, Any], source_root: Path, tool: Path) -> dict[str, Any]:
    executable_hash = arithmetic_obligations.sha256_file(executable)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable does not match Japanese v1.02h")
    if parent.get("kind") != first_item_audit.KIND:
        raise ValueError("wrong parent audit")
    anchors, source_hashes = verify_sources(source_root)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "first_item_artifact_sha256": parent["artifact_sha256"],
            "stage1_ecl_sha256": parent["inputs"]["stage1_ecl_sha256"],
        },
        "generator": {"path": "tools/second_wave_audit.py", "sha256": arithmetic_obligations.sha256_file(tool)},
        "upstream": {
            "url": "https://github.com/GensokyoClub/th06",
            "revision": player_position_audit.UPSTREAM_REVISION,
            "source_files": source_hashes,
            "anchors": anchors,
            "correspondence_status": "source-level correspondence plus paired address-bound differential evidence",
        },
        "derived_profile_contract": {
            "route": "Reimu A, Normal, Stage 1 replay 002677",
            "anchor_game_frame": 249,
            "last_game_frame": 350,
            "timeline_spawns": [257, 273, 289, 305, 321, 337],
            "second_group_deaths": [328, 331, 335, 343, 350],
            "death_player_bullet_slots": [1, 0, 3, 2, 4],
            "death_effect_rng_u16_calls": [55, 25, 25, 55, 25],
            "rng_anchor": {"seed": 41015, "generation": 157},
            "rng_final": {"seed": 37443, "generation": 342},
            "random_drop_items": [
                {"game_frame": 328, "slot": 1, "type": "ITEM_POWER_SMALL"},
                {"game_frame": 343, "slot": 2, "type": "ITEM_POINT"},
            ],
            "enemy_bullets": {
                "active_slots": 0,
                "next_index": 0,
                "count": 0,
                "timer_current_at_end": 350,
                "claim": "complete relocation-free active-slot projection is empty through the checkpoint",
            },
            "effect_slice": (
                "five common effects per death, plus six random-drop effects on cursor multiples of three; "
                "each observed effect consumes one U16 in its ANM random-sprite instruction and four U16 via "
                "two GetRandomU32 splash coordinates in the same frame"
            ),
        },
        "evidence_status": (
            "paired with a 400-frame retail/reference comparison covering Enemy/ECL, Player collisions, Items, "
            "RNG, and the Enemy-bullet manager; a 1200-frame run crosses the first actual Enemy bullets"
        ),
        "open_obligations": [
            "Translate the selected ECL and effect ANM bytecode to a machine-checked decoder correspondence.",
            "Replace the finite effect-pool capacity argument with alias-aware noninterference.",
            "Continue the canonical kernel from frame 350 to the first actual Enemy-bullet spawn at frame 1180.",
        ],
        "counts": {"source_anchors": len(anchors), "incremental_transitions": 101, "enemy_deaths": 5},
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--parent", type=Path, default=Path("arithmetic/first-item-v1.json"))
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()
    document = build(args.executable, load_sealed(args.parent), args.source_root, Path(__file__).resolve())
    rendered = arithmetic_obligations.render(document)
    if args.check:
        if args.check.read_text(encoding="utf-8") != rendered:
            print(f"stale second-wave audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current second-wave audit: {args.check}")
    elif args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output} ({document['artifact_sha256']})")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

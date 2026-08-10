#!/usr/bin/env python3
"""Check the tracked second-wave OpenVM proof bundle."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
MANIFEST = EVIDENCE / "openvm-second-wave-349-v1.json"
VECTOR = EVIDENCE / "second-wave-002677-350-v1.bin"
BUILDER = ROOT / "tools" / "build_second_wave_openvm_input.py"
STATEMENT_DOMAIN = b"zkTH06/openvm/second-wave/v1\0"
SUMMARY = struct.Struct("<4IHI2B2HiH4B2HiH2I32s")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    text = MANIFEST.read_text(encoding="utf-8")
    assert "/home/" not in text
    manifest = json.loads(text)
    assert manifest["type"] == "zkth06.openvm-second-wave-proof"
    assert manifest["schema_version"] == 1
    assert manifest["backend"]["cargo_openvm_version"] == "2.0.1"
    assert manifest["backend"]["cargo_openvm_revision"].startswith("b820b25")
    assert manifest["backend"]["vm_extensions"] == ["rv32i", "rv32m", "io", "sha2"]

    workload = manifest["workload"]
    assert workload["source_vector_sha256"] == sha256(VECTOR)
    assert workload["source_vector_bytes"] == VECTOR.stat().st_size == 47_360
    assert workload["anchor_game_frame"] == 1
    assert workload["incremental_anchor_game_frame"] == 249
    assert workload["final_game_frame"] == 350
    assert workload["transitions"] == 349
    assert workload["incremental_transitions"] == 101
    assert workload["timeline_spawns"] == [257, 273, 289, 305, 321, 337]
    assert workload["enemy_deaths"] == [328, 331, 335, 343, 350]
    assert workload["death_effect_rng_u16_calls"] == [55, 25, 25, 55, 25]
    assert workload["rng_seed"] == 37443
    assert workload["rng_generation"] == 342
    assert workload["random_item_spawn_index"] == 11
    assert workload["random_item_table_index"] == 3
    assert workload["item_allocator_next_index"] == 3
    assert workload["item_count"] == workload["active_items"] == 2
    assert workload["score"] == 3910
    assert workload["remaining_enemies"] == 1
    assert workload["active_enemy_bullets"] == workload["enemy_bullet_count"] == 0
    assert workload["enemy_bullet_timer"] == 350
    assert workload["oracle_first_active_enemy_bullet_frame"] == 1180
    assert workload["oracle_final_active_enemy_bullets"] == 7
    assert workload["input_payload_bytes"] == 724

    for group in ("source_bindings", "evidence_bindings"):
        for relative, expected in manifest[group].items():
            path = ROOT / relative
            assert path.is_file(), relative
            assert sha256(path) == expected, relative
    for relative, expected in manifest["public_values_audit"]["tool_source_bindings"].items():
        assert sha256(ROOT / relative) == expected, relative

    for name in ("vm_executable", "app_verifying_key", "app_commit_descriptor", "app_proof"):
        descriptor = manifest["artifacts"][name]
        path = EVIDENCE / descriptor["path"]
        assert path.is_file(), name
        assert path.stat().st_size == descriptor["bytes"], name
        assert sha256(path) == descriptor["sha256"], name
    commit = json.loads(
        (EVIDENCE / manifest["artifacts"]["app_commit_descriptor"]["path"]).read_text(encoding="utf-8")
    )
    assert commit["app_exe_commit"] == manifest["artifacts"]["vm_executable"]["app_exe_commit"]
    assert commit["app_vm_commit"] == "0x007a02fc3055c8beb7aa51187d008991bdec498852b5e1e27f223ee04a72cac5"

    with tempfile.TemporaryDirectory(prefix="zkth06-second-wave-openvm-") as directory:
        input_path = Path(directory) / "input.json"
        report_path = Path(directory) / "report.json"
        result = subprocess.run(
            ["python3", str(BUILDER), str(VECTOR), str(input_path), "--report", str(report_path)],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(report_path.read_text(encoding="utf-8"))
        encoded = json.loads(input_path.read_text(encoding="utf-8"))["input"][0]
        assert encoded.startswith("0x01")
        payload = bytes.fromhex(encoded[4:])

    report_fields = {
        "source_vector_sha256": "source_vector_sha256",
        "input_payload_bytes": "input_payload_bytes",
        "input_payload_sha256": "input_payload_sha256",
        "expected_final_game_frame": "final_game_frame",
        "incremental_transitions": "incremental_transitions",
        "expected_score": "score",
        "expected_rng_seed": "rng_seed",
        "expected_rng_generation": "rng_generation",
        "expected_random_spawn_index": "random_item_spawn_index",
        "expected_random_table_index": "random_item_table_index",
        "expected_item_next_index": "item_allocator_next_index",
        "expected_item_count": "item_count",
        "expected_active_items": "active_items",
        "expected_active_player_bullets": "active_player_bullets",
        "expected_collided_player_bullets": "collided_player_bullets",
        "expected_remaining_enemies": "remaining_enemies",
        "expected_enemy_bullet_next_index": "enemy_bullet_next_index",
        "expected_enemy_bullet_count": "enemy_bullet_count",
        "expected_enemy_bullet_timer": "enemy_bullet_timer",
        "expected_active_enemy_bullets": "active_enemy_bullets",
        "expected_maximum_enemies": "maximum_enemies",
        "expected_maximum_items": "maximum_items",
        "expected_projection_sha256": "expected_projection_sha256",
        "expected_statement_sha256": "expected_statement_sha256",
    }
    for report_field, workload_field in report_fields.items():
        assert report[report_field] == workload[workload_field], report_field
    summary = SUMMARY.pack(
        workload["final_game_frame"],
        350,
        workload["incremental_transitions"],
        workload["score"],
        workload["rng_seed"],
        workload["rng_generation"],
        workload["random_item_spawn_index"],
        workload["random_item_table_index"],
        workload["item_allocator_next_index"],
        workload["item_count"],
        workload["subrank"],
        workload["current_power"],
        workload["remaining_enemies"],
        workload["active_items"],
        workload["active_player_bullets"],
        workload["collided_player_bullets"],
        workload["enemy_bullet_next_index"],
        workload["enemy_bullet_count"],
        workload["enemy_bullet_timer"],
        workload["active_enemy_bullets"],
        workload["maximum_enemies"],
        workload["maximum_items"],
        bytes.fromhex(workload["expected_projection_sha256"]),
    )
    statement = hashlib.sha256(STATEMENT_DOMAIN + payload + summary).digest()
    assert statement.hex() == workload["expected_statement_sha256"]
    public = manifest["public_values_audit"]
    assert public["decoded_bytes"] == list(statement)
    assert public["matches_expected_statement_sha256"] is True
    assert public["one_bit_wrong_expected_digest_rejected"] is True
    assert manifest["meter"] == [{
        "transitions": 349,
        "incremental_transitions": 101,
        "instructions": 28_003_469,
        "cells": 1_089_931_880,
        "statement_sha256": workload["expected_statement_sha256"],
    }]
    assert all(manifest["verification"].values())
    assert "349 linked" in manifest["claim_boundary"]
    assert "using only replay input masks" in manifest["claim_boundary"]
    assert "explicitly empty Enemy-bullet" in manifest["claim_boundary"]
    assert manifest["backend"]["cargo_openvm_revision"] in (
        ROOT / "zkvm" / "second-wave-openvm" / "Cargo.lock"
    ).read_text(encoding="utf-8")
    print("validated tracked OpenVM second-wave proof bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

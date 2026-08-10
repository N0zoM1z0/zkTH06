#!/usr/bin/env python3
"""Build the path-free manifest for the tracked second-wave OpenVM proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUTPUT = EVIDENCE / "openvm-second-wave-349-v1.json"


def sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def binding(paths: list[str]) -> dict[str, str]:
    return {path: sha256(path) for path in paths}


def descriptor(relative: str) -> dict[str, int | str]:
    path = EVIDENCE / relative
    return {"path": relative, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> int:
    source_paths = [
        "zkvm/player-motion/Cargo.toml",
        "zkvm/player-motion/src/lib.rs",
        "zkvm/player-motion/src/pc24.rs",
        "zkvm/player-shooting/Cargo.toml",
        "zkvm/player-shooting/src/lib.rs",
        "zkvm/player-bullets/Cargo.toml",
        "zkvm/player-bullets/src/lib.rs",
        "zkvm/player-bullet-lifecycle/Cargo.toml",
        "zkvm/player-bullet-lifecycle/src/lib.rs",
        "zkvm/early-gameplay/Cargo.toml",
        "zkvm/early-gameplay/src/lib.rs",
        "zkvm/first-wave/Cargo.toml",
        "zkvm/first-wave/src/lib.rs",
        "zkvm/first-item/Cargo.toml",
        "zkvm/first-item/src/lib.rs",
        "zkvm/second-wave/Cargo.lock",
        "zkvm/second-wave/Cargo.toml",
        "zkvm/second-wave/src/lib.rs",
        "zkvm/second-wave-openvm/Cargo.lock",
        "zkvm/second-wave-openvm/Cargo.toml",
        "zkvm/second-wave-openvm/openvm.toml",
        "zkvm/second-wave-openvm/src/main.rs",
        "tools/build_second_wave_openvm_input.py",
        "reference/src/HeadlessRuntime.cpp",
        "reference/src/ZunMath.hpp",
        "tools/gdb/retail_anchor_trace.py",
        "tools/compare_retail_anchor.py",
    ]
    evidence_paths = [
        "arithmetic/second-wave-v1.json",
        "evidence/retail-reference-002677-1200-enemy-bullets-v1.json",
        "evidence/second-wave-002677-350-v1.bin",
        "evidence/second-wave-002677-350-v1.json",
        "evidence/first-item-002677-249-v1.bin",
        "tools/build_second_wave_vector.py",
        "tools/second_wave_audit.py",
        "tools/build_second_wave_openvm_manifest.py",
    ]
    vector = EVIDENCE / "second-wave-002677-350-v1.bin"
    comparison = json.loads((EVIDENCE / "retail-reference-002677-1200-enemy-bullets-v1.json").read_text(encoding="utf-8"))
    input_report = json.loads((ROOT / "local/validation/openvm-second-wave-input-report.json").read_text(encoding="utf-8"))
    guest_elf = ROOT / "zkvm/second-wave-openvm/target/riscv32im-risc0-zkvm-elf/release/zkth06-second-wave-openvm"
    audit = json.loads((ROOT / "arithmetic/second-wave-v1.json").read_text(encoding="utf-8"))
    manifest = {
        "type": "zkth06.openvm-second-wave-proof",
        "schema_version": 1,
        "date_utc": "2026-08-10",
        "backend": {
            "name": "OpenVM",
            "cargo_openvm_version": "2.0.1",
            "cargo_openvm_revision": "b820b25baab6c5d9b055f64e0286b6b1058e707c",
            "guest_target": "riscv32im-risc0-zkvm-elf",
            "guest_toolchain": "nightly-2026-01-18",
            "guest_rustc": "rustc 1.94.0-nightly (fe98ddcfc 2026-01-17)",
            "vm_extensions": ["rv32i", "rv32m", "io", "sha2"],
        },
        "workload": {
            "source_vector": vector.name,
            "source_vector_bytes": vector.stat().st_size,
            "source_vector_sha256": hashlib.sha256(vector.read_bytes()).hexdigest(),
            "retail_target_executable_sha256": comparison["target_executable_sha256"],
            "replay_sha256": comparison["replay_sha256"],
            "retail_trace_sha256": comparison["retail_trace_sha256"],
            "reference_trace_sha256": comparison["reference_trace_sha256"],
            "retail_reference_comparison_sha256": sha256("evidence/retail-reference-002677-1200-enemy-bullets-v1.json"),
            "static_audit_sha256": sha256("arithmetic/second-wave-v1.json"),
            "static_audit_sealed_digest": audit["artifact_sha256"],
            "parent_first_item_vector_sha256": sha256("evidence/first-item-002677-249-v1.bin"),
            "profile": "normal-reimu-a-power-rank-1-second-enemy-group",
            "source_frames": 1200,
            "anchor_game_frame": 1,
            "incremental_anchor_game_frame": 249,
            "final_game_frame": 350,
            "transitions": 349,
            "incremental_transitions": 101,
            "character": 0,
            "shot_type": 0,
            "difficulty": 1,
            "profile_flags": 15,
            "timeline_spawns": [257, 273, 289, 305, 321, 337],
            "enemy_deaths": [328, 331, 335, 343, 350],
            "death_effect_rng_u16_calls": [55, 25, 25, 55, 25],
            "rng_seed": 37443,
            "rng_generation": 342,
            "random_item_spawn_index": 11,
            "random_item_table_index": 3,
            "item_allocator_next_index": 3,
            "item_count": 2,
            "active_items": 2,
            "current_power": 1,
            "subrank": 1,
            "collided_player_bullets": 4,
            "active_player_bullets": 7,
            "remaining_enemies": 1,
            "maximum_enemies": 5,
            "maximum_items": 2,
            "score": 3910,
            "enemy_bullet_next_index": 0,
            "enemy_bullet_count": 0,
            "enemy_bullet_timer": 350,
            "active_enemy_bullets": 0,
            "oracle_first_active_enemy_bullet_frame": 1180,
            "oracle_final_active_enemy_bullets": 7,
            "input_payload_bytes": input_report["input_payload_bytes"],
            "input_payload_sha256": input_report["input_payload_sha256"],
            "expected_projection_sha256": input_report["expected_projection_sha256"],
            "state_domain_ascii": input_report["state_domain_ascii"],
            "state_domain_nul_terminated": True,
            "statement_domain_ascii": input_report["statement_domain_ascii"],
            "statement_domain_nul_terminated": True,
            "expected_statement_sha256": input_report["expected_statement_sha256"],
            "statement_preimage": "domain || input_payload || final_game_frame_le || input_frames_le || incremental_transitions_le || score_le || rng_seed_le_u16 || rng_generation_le || random_spawn_index_u8 || random_table_index_u8 || item_next_index_le_u16 || item_count_le_u16 || subrank_le_i32 || power_le_u16 || final_entity_counts_u8 || enemy_bullet_manager || maxima_le_u32 || projection_sha256",
        },
        "source_bindings": binding(source_paths),
        "evidence_bindings": binding(evidence_paths),
        "artifacts": {
            "guest_elf": {
                "bytes": guest_elf.stat().st_size,
                "sha256": hashlib.sha256(guest_elf.read_bytes()).hexdigest(),
                "tracked": False,
            },
            "vm_executable": {
                **descriptor("second-wave-v1/zkth06-second-wave-openvm.vmexe"),
                "app_exe_commit": "0x002bb8c7af371560e154f6db1cf188a55b64a42da1e20c657350275f2095ce73",
            },
            "app_proving_key": {
                "bytes": (ROOT / "zkvm/second-wave-openvm/openvm/app.pk").stat().st_size,
                "tracked": False,
                "reason": "deterministically regenerable and not required for verification",
            },
            "app_verifying_key": descriptor("second-wave-v1/app.vk"),
            "app_commit_descriptor": descriptor("second-wave-v1/app-commit.json"),
            "app_proof": descriptor("openvm-second-wave-349-v1.app.proof"),
        },
        "meter": [{
            "transitions": 349,
            "incremental_transitions": 101,
            "instructions": 28003469,
            "cells": 1089931880,
            "statement_sha256": input_report["expected_statement_sha256"],
        }],
        "public_values_audit": {
            "method": "OpenVM v2.0.1 SDK deserialization as ContinuationVmProof<SC>",
            "tool_source_bindings": binding([
                "tools/openvm-proof-inspect/Cargo.lock",
                "tools/openvm-proof-inspect/Cargo.toml",
                "tools/openvm-proof-inspect/src/main.rs",
            ]),
            "decoded_bytes": list(bytes.fromhex(input_report["expected_statement_sha256"])),
            "matches_expected_statement_sha256": True,
            "one_bit_wrong_expected_digest_rejected": True,
        },
        "proving": {
            "elapsed_seconds": 243.25,
            "user_cpu_seconds": 7685.55,
            "system_cpu_seconds": 823.20,
            "cpu_utilization_percent": 3497,
            "max_rss_kib": 52391412,
            "swaps": 0,
            "exit_status": 0,
        },
        "verification": {
            "elapsed_seconds": 0.24,
            "max_rss_kib": 53496,
            "expected_executable_commit_accepted": True,
            "one_bit_wrong_executable_commit_rejected": True,
            "public_statement_digest_matches": True,
            "one_bit_wrong_public_digest_rejected": True,
        },
        "design_iteration": {
            "previous_first_item_payload_bytes": 520,
            "second_wave_payload_bytes": 724,
            "payload_increase_bytes": 204,
            "previous_first_item_instructions": 29288817,
            "second_wave_instructions": 28003469,
            "instruction_change": -1285348,
            "previous_first_item_cells": 1146265201,
            "second_wave_cells": 1089931880,
            "cell_change": -56323321,
            "comparison_note": "The guest recomputes the complete frame-1-to-249 anchor but hashes only the new frame-250-to-350 canonical projection; determinism plus the input/final commitment preserves linkage while avoiding rehashing the parent projection.",
        },
        "claim_boundary": "This proof starts from the fixed empty gameplay-frame-1 state and executes 349 linked Normal Reimu-A power-rank-1 transitions using only replay input masks. It derives the complete frame-249 parent state, then six second-group Enemy spawns, ECL timers and movement, five deaths, effect RNG consumption, two random-drop Items, allocator cursors, score 3910, and explicitly empty Enemy-bullet manager/pool state through frame 350. Every retained Player bullet, Enemy, Item, RNG, score, cursor, and Enemy-bullet field is publicly committed for frames 250 through 350. Retail Wine and the independently built Linux reference match the enlarged projection over 1200 frames and cross the first seven active Enemy bullets at frame 1180. This is finite differential and static-mapping evidence, not a universal retail-binary equivalence proof. The kernel fails closed if the last frame-328 Enemy survives into its unsupported next trigonometric write. Direct ECL/effect ANM decoding, general x87 transcendental refinement, alias-complete omitted-path noninterference, source/binary/guest correspondence, live Enemy bullets after frame 350, and later gameplay subsystems remain explicit obligations.",
    }
    rendered = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    if "/home/" in rendered:
        raise AssertionError("manifest contains local absolute path")
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": "built", "path": str(OUTPUT.relative_to(ROOT))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

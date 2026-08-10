#!/usr/bin/env python3
"""Exercise the retail/reference anchor comparator without proprietary data."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARATOR = ROOT / "tools" / "compare_retail_anchor.py"
EVIDENCE = ROOT / "evidence" / "retail-reference-002677-2000-v1.json"
SHOOTING_EVIDENCE = ROOT / "evidence" / "retail-reference-002677-2000-shooting-v1.json"
PLAYER_BULLETS_EVIDENCE = (
    ROOT / "evidence" / "retail-reference-002677-2000-player-bullets-v1.json"
)
ENEMY_COLLISION_EVIDENCE = (
    ROOT / "evidence" / "retail-reference-002677-225-enemy-collisions-v1.json"
)
ITEM_EVIDENCE = ROOT / "evidence" / "retail-reference-002677-300-items-v1.json"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def retail_frame() -> dict[str, object]:
    return {
        "type": "zkth06.retail-anchor-frame",
        "index": 0,
        "supervisor_state": 2,
        "stage": 1,
        "game_frame": 1,
        "difficulty": 3,
        "character": 0,
        "shot_type": 1,
        "input": 0,
        "rng_seed": 28967,
        "rng_generation": 2,
        "score": 0,
        "deaths": 0,
        "bombs_used": 0,
        "is_time_stopped": 0,
        "num_retries": 0,
        "current_power": 0,
        "lives": 2,
        "bombs": 3,
        "rank": 1,
        "subrank": 10,
        "player_state": 3,
        "player_x_bits": "0x43400000",
        "player_y_bits": "0x43c00000",
        "player_z_bits": "0x3efae148",
        "movement_min_x_bits": "0x41000000",
        "movement_min_y_bits": "0x41800000",
        "movement_size_x_bits": "0x43b80000",
        "movement_size_y_bits": "0x43d00000",
        "horizontal_multiplier_bits": "0x3f800000",
        "vertical_multiplier_bits": "0x3f800000",
        "orthogonal_speed_bits": "0x40800000",
        "orthogonal_focus_speed_bits": "0x40000000",
        "diagonal_speed_bits": "0x403504f3",
        "diagonal_focus_speed_bits": "0x3fb504f3",
        "effective_rate_bits": "0x3f800000",
        "x87_control_word": "0x007f",
        "mxcsr": "0x00001fa0",
    }


def reference_frame() -> dict[str, object]:
    return {
        "tick": 1,
        "scope": {"difficulty": 3, "character": 0, "shot_type": 1},
        "supervisor_state": 2,
        "stage": 1,
        "game_frame": 1,
        "rng_seed": 28967,
        "rng_generation": 2,
        "input": 0,
        "is_time_stopped": 0,
        "effective_rate_bits": 0x3F800000,
        "movement_min_x_bits": 0x41000000,
        "movement_min_y_bits": 0x41800000,
        "movement_size_x_bits": 0x43B80000,
        "movement_size_y_bits": 0x43D00000,
        "player": {
            "x_bits": 0x43400000,
            "y_bits": 0x43C00000,
            "z_bits": 0x3EFAE148,
            "state": 3,
            "horizontal_multiplier_bits": 0x3F800000,
            "vertical_multiplier_bits": 0x3F800000,
            "orthogonal_speed_bits": 0x40800000,
            "orthogonal_focus_speed_bits": 0x40000000,
            "diagonal_speed_bits": 0x403504F3,
            "diagonal_focus_speed_bits": 0x3FB504F3,
        },
        "lives": 2,
        "bombs": 3,
        "score": 0,
        "deaths": 0,
        "bombs_used": 0,
        "num_retries": 0,
        "current_power": 0,
        "rank": 1,
        "subrank": 10,
    }


def run_comparator(
    retail: Path,
    reference: Path,
    report: Path,
    *,
    enclosing_player: bool = False,
    player_shooting: bool = False,
    player_bullets: bool = False,
    player_bullet_frames: bool = False,
    enemy_collisions: bool = False,
    items: bool = False,
    enemy_bullets: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(COMPARATOR), str(retail), str(reference), "--report", str(report)]
    if enclosing_player:
        command.append("--enclosing-player")
    if player_shooting:
        command.append("--player-shooting")
    if player_bullets:
        command.append("--player-bullets")
    if player_bullet_frames:
        command.append("--player-bullet-frames")
    if enemy_collisions:
        command.append("--enemy-collisions")
    if items:
        command.append("--items")
    if enemy_bullets:
        command.append("--enemy-bullets")
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )


def main() -> int:
    evidence_text = EVIDENCE.read_text(encoding="utf-8")
    assert "/home/" not in evidence_text
    committed_evidence = json.loads(evidence_text)
    assert committed_evidence["status"] == "match"
    assert committed_evidence["compared_frames"] == 2000
    assert len(committed_evidence["compared_fields"]) == 34
    assert committed_evidence["target_executable_sha256"] == TARGET_SHA256
    assert committed_evidence["replay_sha256"] == (
        "01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f"
    )
    assert committed_evidence["retail_x87_control_words"] == ["0x007f"]
    assert committed_evidence["retail_mxcsr_values"] == ["0x00001fa0"]
    assert committed_evidence["observed_retail_metrics"] == {
        "distinct_input_masks": 27,
        "final_score": 767990,
        "first_game_frame": 1,
        "last_game_frame": 2000,
        "rng_generation_max": 3555,
        "rng_generation_min": 2,
    }
    shooting_evidence_text = SHOOTING_EVIDENCE.read_text(encoding="utf-8")
    assert "/home/" not in shooting_evidence_text
    shooting_evidence = json.loads(shooting_evidence_text)
    assert shooting_evidence["status"] == "match"
    assert shooting_evidence["comparison_profile"] == "player-shooting"
    assert shooting_evidence["compared_frames"] == 2_000
    assert len(shooting_evidence["compared_fields"]) == 46
    player_bullets_evidence_text = PLAYER_BULLETS_EVIDENCE.read_text(encoding="utf-8")
    assert "/home/" not in player_bullets_evidence_text
    player_bullets_evidence = json.loads(player_bullets_evidence_text)
    assert player_bullets_evidence["status"] == "match"
    assert player_bullets_evidence["comparison_profile"] == "player-bullets"
    assert player_bullets_evidence["compared_frames"] == 2_000
    assert len(player_bullets_evidence["compared_fields"]) == 47
    enemy_collision_evidence_text = ENEMY_COLLISION_EVIDENCE.read_text(encoding="utf-8")
    assert "/home/" not in enemy_collision_evidence_text
    enemy_collision_evidence = json.loads(enemy_collision_evidence_text)
    assert enemy_collision_evidence["status"] == "match"
    assert enemy_collision_evidence["comparison_profile"] == "enemy-collisions"
    assert enemy_collision_evidence["compared_frames"] == 225
    assert enemy_collision_evidence["observed_enemy_collision_metrics"] == {
        "damage_calls": 249,
        "damaging_calls": 4,
        "first_damaging_game_frame": 208,
        "maximum_active_enemies": 5,
        "trace_overflow_frames": 0,
    }
    item_evidence_text = ITEM_EVIDENCE.read_text(encoding="utf-8")
    assert "/home/" not in item_evidence_text
    item_evidence = json.loads(item_evidence_text)
    assert item_evidence["status"] == "match"
    assert item_evidence["comparison_profile"] == "items"
    assert item_evidence["compared_frames"] == 300
    assert item_evidence["observed_item_metrics"] == {
        "first_active_game_frame": 219,
        "first_collection_game_frame": 249,
        "maximum_active_items": 1,
    }

    header = {
        "type": "zkth06.retail-anchor-header",
        "schema_version": 1,
        "target_executable_sha256": TARGET_SHA256,
        "replay_sha256": "a" * 64,
        "config_sha256": "b" * 64,
        "wine_version": "wine-test",
        "gdb_version": "gdb-test",
        "frame_boundary": "0x00420858",
        "frame_boundary_role": "instruction after Chain::RunCalcChain",
    }
    with tempfile.TemporaryDirectory(prefix="zkth06-retail-test-") as directory:
        temporary = Path(directory)
        retail = temporary / "retail.jsonl"
        reference = temporary / "reference.jsonl"
        report = temporary / "report.json"
        write_jsonl(retail, [header, retail_frame()])
        write_jsonl(reference, [reference_frame()])

        matched = run_comparator(retail, reference, report)
        assert matched.returncode == 0, matched.stderr
        assert matched.stdout.strip() == "matched 1 retail/reference anchor frames"
        evidence = json.loads(report.read_text(encoding="utf-8"))
        assert evidence["status"] == "match"
        assert evidence["compared_frames"] == 1
        assert evidence["first_mismatch"] is None
        assert evidence["retail_x87_control_words"] == ["0x007f"]
        assert evidence["retail_mxcsr_values"] == ["0x00001fa0"]
        assert str(temporary) not in report.read_text(encoding="utf-8")

        enclosing_retail = retail_frame()
        enclosing_retail.update(
            {
                "framerate_multiplier_bits": "0x3f800000",
                "player_respawn_timer": 6,
                "player_bomb_is_in_use": 0,
                "player_invulnerability_timer_previous": -999,
                "player_invulnerability_timer_subframe_bits": "0x00000000",
                "player_invulnerability_timer_current": 239,
            }
        )
        enclosing_reference = reference_frame()
        enclosing_reference["framerate_multiplier_bits"] = 0x3F800000
        enclosing_reference["player"].update(
            {
                "respawn_timer": 6,
                "bomb_is_in_use": 0,
                "invulnerability_timer_previous": -999,
                "invulnerability_timer_subframe_bits": 0,
                "invulnerability_timer_current": 239,
            }
        )
        write_jsonl(retail, [header, enclosing_retail])
        write_jsonl(reference, [enclosing_reference])
        enclosing = run_comparator(retail, reference, report, enclosing_player=True)
        assert enclosing.returncode == 0, enclosing.stderr
        enclosing_evidence = json.loads(report.read_text(encoding="utf-8"))
        assert enclosing_evidence["comparison_profile"] == "enclosing-player"
        assert len(enclosing_evidence["compared_fields"]) == 40

        shooting_retail = dict(enclosing_retail)
        shooting_retail.update(
            {
                "gui_has_current_message": 0,
                "player_is_focus": 0,
                "player_previous_frame_input": 0,
                "player_fire_bullet_timer_previous": -999,
                "player_fire_bullet_timer_subframe_bits": "0x00000000",
                "player_fire_bullet_timer_current": -1,
            }
        )
        shooting_reference = dict(enclosing_reference)
        shooting_reference["player"] = dict(enclosing_reference["player"])
        shooting_reference["gui_has_current_message"] = 0
        shooting_reference["player"].update(
            {
                "is_focus": 0,
                "previous_frame_input": 0,
                "fire_bullet_timer_previous": -999,
                "fire_bullet_timer_subframe_bits": 0,
                "fire_bullet_timer_current": -1,
            }
        )
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        shooting = run_comparator(retail, reference, report, player_shooting=True)
        assert shooting.returncode == 0, shooting.stderr
        shooting_report = json.loads(report.read_text(encoding="utf-8"))
        assert shooting_report["comparison_profile"] == "player-shooting"
        assert len(shooting_report["compared_fields"]) == 46

        spawn_projection = {
            "timer": 0,
            "current_power": 0,
            "before": {"slot_states": [0, 1]},
            "after": {"slot_states": [1, 1]},
        }
        shooting_retail["player_spawn"] = spawn_projection
        shooting_reference["player_spawn"] = spawn_projection
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        bullets = run_comparator(retail, reference, report, player_bullets=True)
        assert bullets.returncode == 0, bullets.stderr
        bullets_report = json.loads(report.read_text(encoding="utf-8"))
        assert bullets_report["comparison_profile"] == "player-bullets"
        assert len(bullets_report["compared_fields"]) == 47

        bullet_side = {
            "slot_states": [1, 0],
            "active_slots": [{"slot": 0, "state": 1, "type": 0}],
            "slot_carry": [{"slot": 0, "state": 1}, {"slot": 1, "state": 0}],
        }
        bullet_update = {
            "last_enemy_hit_bits": ["0xc479c000", "0xc479c000", "0x00000000"],
            "before": bullet_side,
            "after": bullet_side,
        }
        shooting_retail.update(
            {
                "player_bullet_update": bullet_update,
                "player_last_enemy_hit_bits": [
                    "0xc479c000",
                    "0xc479c000",
                    "0x00000000",
                ],
                "player_bullets_frame": bullet_side,
            }
        )
        shooting_reference.update(
            {
                "player_bullet_update": bullet_update,
                "player_last_enemy_hit_bits": [
                    "0xc479c000",
                    "0xc479c000",
                    "0x00000000",
                ],
                "player_bullets_frame": bullet_side,
            }
        )
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        bullet_frames = run_comparator(
            retail, reference, report, player_bullet_frames=True
        )
        assert bullet_frames.returncode == 0, bullet_frames.stderr
        bullet_frames_report = json.loads(report.read_text(encoding="utf-8"))
        assert bullet_frames_report["comparison_profile"] == "player-bullet-frames"
        assert len(bullet_frames_report["compared_fields"]) == 50
        assert bullet_frames_report["semantic_projection_exclusions"][0][
            "observed_differences"
        ] == 0

        enemy = {
            "slot": 0,
            "x": 60,
            "y": -30,
            "position_bits": ["0x42700000", "0xc1f00000", "0x00000000"],
            "hitbox_bits": ["0x41e00000", "0x41e00000", "0x42000000"],
        }
        damage_call = {
            "enemy_position_bits": enemy["position_bits"],
            "enemy_hitbox_bits": enemy["hitbox_bits"],
            "bomb_is_in_use": 0,
            "damage": 0,
            "hit_with_laser_during_bomb": False,
            "before": bullet_side,
            "after": bullet_side,
        }
        shooting_retail.update(
            {
                "enemies": [enemy],
                "player_damage_calls": [damage_call],
                "player_damage_trace_overflow": False,
            }
        )
        shooting_reference.update(
            {
                "enemies": [{**enemy, "x": 60.0, "y": -30.0}],
                "player_damage_calls": [damage_call],
                "player_damage_trace_overflow": False,
            }
        )
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        enemy_collisions = run_comparator(
            retail, reference, report, enemy_collisions=True
        )
        assert enemy_collisions.returncode == 0, enemy_collisions.stderr
        enemy_report = json.loads(report.read_text(encoding="utf-8"))
        assert enemy_report["comparison_profile"] == "enemy-collisions"
        assert len(enemy_report["compared_fields"]) == 53
        assert enemy_report["observed_enemy_collision_metrics"]["damage_calls"] == 1

        item_projection = {
            "next_index": 1,
            "item_count": 1,
            "random_spawn_index": 4,
            "random_table_index": 1,
            "active_slots": [
                {
                    "slot": 0,
                    "current_position_bits": ["0x42700000", "0xc1f00000", "0x00000000"],
                    "start_position_bits": ["0x00000000", "0xc00ccccd", "0x00000000"],
                    "target_position_bits": ["0x00000000", "0x00000000", "0x00000000"],
                    "timer_previous": 0,
                    "timer_subframe_bits": "0x00000000",
                    "timer_current": 1,
                    "item_type": 0,
                    "is_in_use": 1,
                    "unk_142": 1,
                    "state": 0,
                }
            ],
        }
        shooting_retail["items_frame"] = item_projection
        shooting_reference["items_frame"] = json.loads(json.dumps(item_projection))

        enemy_bullet_projection = {
            "next_index": 1,
            "bullet_count": 1,
            "timer_previous": 0,
            "timer_subframe_bits": "0x00000000",
            "timer_current": 1,
            "active_slots": [
                {
                    "slot": 0,
                    "state": 2,
                    "position_bits": ["0x437c0000", "0x42980000", "0x3dcccccd"],
                }
            ],
        }
        shooting_retail["enemy_bullets_frame"] = enemy_bullet_projection
        shooting_reference["enemy_bullets_frame"] = json.loads(
            json.dumps(enemy_bullet_projection)
        )
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        enemy_bullets = run_comparator(
            retail, reference, report, enemy_bullets=True
        )
        assert enemy_bullets.returncode == 0, enemy_bullets.stderr
        enemy_bullet_report = json.loads(report.read_text(encoding="utf-8"))
        assert enemy_bullet_report["comparison_profile"] == "enemy-bullets"
        assert len(enemy_bullet_report["compared_fields"]) == 55
        assert enemy_bullet_report["observed_enemy_bullet_metrics"] == {
            "first_active_game_frame": 1,
            "maximum_active_bullets": 1,
            "final_active_bullets": 1,
        }

        shooting_reference["enemy_bullets_frame"]["active_slots"][0]["state"] = 1
        write_jsonl(reference, [shooting_reference])
        enemy_bullet_mismatch = run_comparator(
            retail, reference, report, enemy_bullets=True
        )
        assert enemy_bullet_mismatch.returncode == 1
        enemy_bullet_nested = json.loads(report.read_text(encoding="utf-8"))[
            "first_mismatch"
        ]["differing_fields"]["enemy_bullets_frame"]
        assert enemy_bullet_nested["path"] == "enemy_bullets_frame.active_slots[0].state"
        shooting_reference["enemy_bullets_frame"] = json.loads(
            json.dumps(enemy_bullet_projection)
        )
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        items = run_comparator(retail, reference, report, items=True)
        assert items.returncode == 0, items.stderr
        item_report = json.loads(report.read_text(encoding="utf-8"))
        assert item_report["comparison_profile"] == "items"
        assert len(item_report["compared_fields"]) == 54
        assert item_report["observed_item_metrics"] == {
            "first_active_game_frame": 1,
            "first_collection_game_frame": None,
            "maximum_active_items": 1,
        }

        shooting_reference["items_frame"]["active_slots"][0]["state"] = 1
        write_jsonl(reference, [shooting_reference])
        item_mismatch = run_comparator(retail, reference, report, items=True)
        assert item_mismatch.returncode == 1
        item_nested = json.loads(report.read_text(encoding="utf-8"))["first_mismatch"][
            "differing_fields"
        ]["items_frame"]
        assert item_nested["path"] == "items_frame.active_slots[0].state"
        shooting_reference["items_frame"] = json.loads(json.dumps(item_projection))

        shooting_reference["items_frame"]["active_slots"][0]["unk_142"] = 0
        write_jsonl(reference, [shooting_reference])
        item_draw_only = run_comparator(retail, reference, report, items=True)
        assert item_draw_only.returncode == 0, item_draw_only.stderr
        item_draw_report = json.loads(report.read_text(encoding="utf-8"))
        assert item_draw_report["semantic_projection_exclusions"][-1] == {
            "path": "items_frame.active_slots[*].unk_142",
            "observed_differences": 1,
            "reason": (
                "ItemManager::OnDraw toggles unk_142 only when selecting the offscreen "
                "indicator sprite; no calc-chain function reads this field"
            ),
        }
        shooting_reference["items_frame"] = json.loads(json.dumps(item_projection))

        shooting_reference["player_damage_calls"] = [{**damage_call, "damage": 48}]
        write_jsonl(reference, [shooting_reference])
        enemy_mismatch = run_comparator(
            retail, reference, report, enemy_collisions=True
        )
        assert enemy_mismatch.returncode == 1
        enemy_nested = json.loads(report.read_text(encoding="utf-8"))["first_mismatch"][
            "differing_fields"
        ]["player_damage_calls"]
        assert enemy_nested["path"] == "player_damage_calls[0].damage"

        shooting_reference["player_bullet_update"] = {
            **bullet_update,
            "before": {
                **bullet_side,
                "active_slots": [
                    {
                        **bullet_side["active_slots"][0],
                        "sprite_position_bits": [
                            "0x00000000",
                            "0x00000000",
                            "0x3dcccccd",
                        ],
                    }
                ],
            },
        }
        shooting_retail["player_bullet_update"] = {
            **bullet_update,
            "before": {
                **bullet_side,
                "active_slots": [
                    {
                        **bullet_side["active_slots"][0],
                        "sprite_position_bits": [
                            "0x00000000",
                            "0x00000000",
                            "0x3ecccccd",
                        ],
                    }
                ],
            },
        }
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        fired_z_difference = run_comparator(
            retail, reference, report, player_bullet_frames=True
        )
        assert fired_z_difference.returncode == 1

        for row in (shooting_retail, shooting_reference):
            before = row["player_bullet_update"]["before"]
            before["slot_states"] = [2, 0]
            before["active_slots"][0]["state"] = 2
            before["slot_carry"][0]["state"] = 2
        write_jsonl(retail, [header, shooting_retail])
        write_jsonl(reference, [shooting_reference])
        draw_only_difference = run_comparator(
            retail, reference, report, player_bullet_frames=True
        )
        assert draw_only_difference.returncode == 0, draw_only_difference.stderr
        draw_only_report = json.loads(report.read_text(encoding="utf-8"))
        assert draw_only_report["semantic_projection_exclusions"][0][
            "observed_differences"
        ] == 1

        shooting_reference["player_bullet_update"] = {
            **bullet_update,
            "after": {
                **bullet_side,
                "slot_states": [0, 0],
            },
        }
        write_jsonl(reference, [shooting_reference])
        bullet_frames_mismatch = run_comparator(
            retail, reference, report, player_bullet_frames=True
        )
        assert bullet_frames_mismatch.returncode == 1
        bullet_frames_mismatch_report = json.loads(report.read_text(encoding="utf-8"))
        nested = bullet_frames_mismatch_report["first_mismatch"]["differing_fields"][
            "player_bullet_update"
        ]
        assert nested["path"] == "player_bullet_update.after.slot_states[0]"
        assert nested["retail"] == 1 and nested["reference"] == 0

        shooting_reference["player_spawn"] = {
            **spawn_projection,
            "after": {"slot_states": [1, 0]},
        }
        write_jsonl(reference, [shooting_reference])
        bullets_mismatch = run_comparator(retail, reference, report, player_bullets=True)
        assert bullets_mismatch.returncode == 1
        bullets_mismatch_report = json.loads(report.read_text(encoding="utf-8"))
        nested = bullets_mismatch_report["first_mismatch"]["differing_fields"]["player_spawn"]
        assert nested["path"] == "player_spawn.after.slot_states[1]"
        assert nested["retail"] == 1 and nested["reference"] == 0

        mismatching = retail_frame()
        mismatching["player_x_bits"] = "0x43400001"
        write_jsonl(retail, [header, mismatching])
        mismatch = run_comparator(retail, reference, report)
        assert mismatch.returncode == 1
        evidence = json.loads(report.read_text(encoding="utf-8"))
        assert evidence["status"] == "mismatch"
        assert evidence["first_mismatch"]["first_mismatch_index"] == 0
        assert evidence["first_mismatch"]["differing_fields"] == {
            "player_x_bits": {"reference": 0x43400000, "retail": 0x43400001}
        }

    print("validated retail-anchor match, report, and first-mismatch behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(COMPARATOR), str(retail), str(reference), "--report", str(report)]
    if enclosing_player:
        command.append("--enclosing-player")
    if player_shooting:
        command.append("--player-shooting")
    if player_bullets:
        command.append("--player-bullets")
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

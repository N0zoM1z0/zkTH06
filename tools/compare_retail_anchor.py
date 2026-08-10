#!/usr/bin/env python3
"""Compare a retail GDB anchor trace with the Linux reference JSON trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 1
HEADER_KIND = "zkth06.retail-anchor-header"
FRAME_KIND = "zkth06.retail-anchor-frame"
TARGET_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
COMMON_FIELDS = (
    "supervisor_state",
    "stage",
    "game_frame",
    "difficulty",
    "character",
    "shot_type",
    "input",
    "rng_seed",
    "rng_generation",
    "score",
    "deaths",
    "bombs_used",
    "is_time_stopped",
    "num_retries",
    "current_power",
    "lives",
    "bombs",
    "rank",
    "subrank",
    "player_state",
    "player_x_bits",
    "player_y_bits",
    "player_z_bits",
    "effective_rate_bits",
    "movement_min_x_bits",
    "movement_min_y_bits",
    "movement_size_x_bits",
    "movement_size_y_bits",
    "horizontal_multiplier_bits",
    "vertical_multiplier_bits",
    "orthogonal_speed_bits",
    "orthogonal_focus_speed_bits",
    "diagonal_speed_bits",
    "diagonal_focus_speed_bits",
)

ENCLOSING_PLAYER_FIELDS = (
    "framerate_multiplier_bits",
    "player_respawn_timer",
    "player_bomb_is_in_use",
    "player_invulnerability_timer_previous",
    "player_invulnerability_timer_subframe_bits",
    "player_invulnerability_timer_current",
)

PLAYER_SHOOTING_FIELDS = (
    "gui_has_current_message",
    "player_is_focus",
    "player_previous_frame_input",
    "player_fire_bullet_timer_previous",
    "player_fire_bullet_timer_subframe_bits",
    "player_fire_bullet_timer_current",
)

DRAW_ONLY_UPDATE_INPUT = (
    "player_bullet_update.before.active_slots[*].sprite_position_bits[2]"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"non-object JSON row at {path}:{line_number}")
        rows.append(row)
    return rows


def normalize_retail(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, int]:
    hex_fields = (
        "player_x_bits",
        "player_y_bits",
        "player_z_bits",
        "effective_rate_bits",
        "movement_min_x_bits",
        "movement_min_y_bits",
        "movement_size_x_bits",
        "movement_size_y_bits",
        "horizontal_multiplier_bits",
        "vertical_multiplier_bits",
        "orthogonal_speed_bits",
        "orthogonal_focus_speed_bits",
        "diagonal_speed_bits",
        "diagonal_focus_speed_bits",
        "framerate_multiplier_bits",
        "player_invulnerability_timer_subframe_bits",
        "player_fire_bullet_timer_subframe_bits",
    )
    normalized = {
        key: int(row[key]) for key in fields if key not in hex_fields
    }
    normalized.update({key: int(row[key], 16) for key in fields if key in hex_fields})
    return normalized


def normalize_reference(
    row: dict[str, Any], enclosing_player: bool, player_shooting: bool
) -> dict[str, int]:
    player = row["player"]
    scope = row["scope"]
    normalized = {
        "supervisor_state": int(row["supervisor_state"]),
        "stage": int(row["stage"]),
        "game_frame": int(row["game_frame"]),
        "difficulty": int(scope["difficulty"]),
        "character": int(scope["character"]),
        "shot_type": int(scope["shot_type"]),
        "input": int(row["input"]),
        "rng_seed": int(row["rng_seed"]),
        "rng_generation": int(row["rng_generation"]),
        "score": int(row["score"]),
        "deaths": int(row["deaths"]),
        "bombs_used": int(row["bombs_used"]),
        "is_time_stopped": int(row["is_time_stopped"]),
        "num_retries": int(row["num_retries"]),
        "current_power": int(row["current_power"]),
        "lives": int(row["lives"]),
        "bombs": int(row["bombs"]),
        "rank": int(row["rank"]),
        "subrank": int(row["subrank"]),
        "player_state": int(player["state"]),
        "player_x_bits": int(player["x_bits"]),
        "player_y_bits": int(player["y_bits"]),
        "player_z_bits": int(player["z_bits"]),
        "effective_rate_bits": int(row["effective_rate_bits"]),
        "movement_min_x_bits": int(row["movement_min_x_bits"]),
        "movement_min_y_bits": int(row["movement_min_y_bits"]),
        "movement_size_x_bits": int(row["movement_size_x_bits"]),
        "movement_size_y_bits": int(row["movement_size_y_bits"]),
        "horizontal_multiplier_bits": int(player["horizontal_multiplier_bits"]),
        "vertical_multiplier_bits": int(player["vertical_multiplier_bits"]),
        "orthogonal_speed_bits": int(player["orthogonal_speed_bits"]),
        "orthogonal_focus_speed_bits": int(player["orthogonal_focus_speed_bits"]),
        "diagonal_speed_bits": int(player["diagonal_speed_bits"]),
        "diagonal_focus_speed_bits": int(player["diagonal_focus_speed_bits"]),
    }
    if enclosing_player:
        normalized.update(
            {
                "framerate_multiplier_bits": int(row["framerate_multiplier_bits"]),
                "player_respawn_timer": int(player["respawn_timer"]),
                "player_bomb_is_in_use": int(player["bomb_is_in_use"]),
                "player_invulnerability_timer_previous": int(
                    player["invulnerability_timer_previous"]
                ),
                "player_invulnerability_timer_subframe_bits": int(
                    player["invulnerability_timer_subframe_bits"]
                ),
                "player_invulnerability_timer_current": int(
                    player["invulnerability_timer_current"]
                ),
            }
        )
    if player_shooting:
        normalized.update(
            {
                "gui_has_current_message": int(row["gui_has_current_message"]),
                "player_is_focus": int(player["is_focus"]),
                "player_previous_frame_input": int(player["previous_frame_input"]),
                "player_fire_bullet_timer_previous": int(
                    player["fire_bullet_timer_previous"]
                ),
                "player_fire_bullet_timer_subframe_bits": int(
                    player["fire_bullet_timer_subframe_bits"]
                ),
                "player_fire_bullet_timer_current": int(
                    player["fire_bullet_timer_current"]
                ),
            }
        )
    return normalized


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def first_nested_difference(
    left: Any,
    right: Any,
    path: str = "player_spawn",
    *,
    ignore_leaf: Callable[[str, Any, Any], bool] | None = None,
    ignored_count: list[int] | None = None,
) -> dict[str, Any] | None:
    if type(left) is not type(right):
        return {"path": path, "retail": left, "reference": right}
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return {
                "path": path,
                "retail_keys": sorted(left),
                "reference_keys": sorted(right),
            }
        for key in left:
            difference = first_nested_difference(
                left[key],
                right[key],
                f"{path}.{key}",
                ignore_leaf=ignore_leaf,
                ignored_count=ignored_count,
            )
            if difference is not None:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return {"path": path, "retail_length": len(left), "reference_length": len(right)}
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = first_nested_difference(
                left_item,
                right_item,
                f"{path}[{index}]",
                ignore_leaf=ignore_leaf,
                ignored_count=ignored_count,
            )
            if difference is not None:
                return difference
        return None
    if left != right:
        if ignore_leaf is not None and ignore_leaf(path, left, right):
            if ignored_count is not None:
                ignored_count[0] += 1
            return None
        return {"path": path, "retail": left, "reference": right}
    return None


def is_draw_only_update_input(path: str) -> int | None:
    prefix = "player_bullet_update.before.active_slots["
    suffix = "].sprite_position_bits[2]"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    slot_index = path[len(prefix) : -len(suffix)]
    return int(slot_index) if slot_index.isdigit() else None


def draw_only_update_input_filter(
    retail_update: Any, reference_update: Any
) -> Callable[[str, Any, Any], bool]:
    def ignore(path: str, _retail_value: Any, _reference_value: Any) -> bool:
        index = is_draw_only_update_input(path)
        if index is None:
            return False
        try:
            retail_bullet = retail_update["before"]["active_slots"][index]
            reference_bullet = reference_update["before"]["active_slots"][index]
            return (
                int(retail_bullet["state"]) == 2
                and int(reference_bullet["state"]) == 2
                and int(retail_bullet["slot"]) == int(reference_bullet["slot"])
            )
        except (IndexError, KeyError, TypeError, ValueError):
            return False

    return ignore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--report", type=Path, help="write a path-free JSON evidence summary")
    parser.add_argument(
        "--enclosing-player",
        action="store_true",
        help="also compare timer, bomb-state, and configured-rate fields",
    )
    parser.add_argument(
        "--player-shooting",
        action="store_true",
        help="also compare the enclosing profile and Player shooting cadence fields",
    )
    parser.add_argument(
        "--player-bullets",
        action="store_true",
        help="also compare address-bound Player::SpawnBullets pre/post slot projections",
    )
    parser.add_argument(
        "--player-bullet-frames",
        action="store_true",
        help="also compare complete post-calc Player-bullet slot projections",
    )
    parser.add_argument(
        "--enemy-collisions",
        action="store_true",
        help="also compare raw Enemy/ECL state and every CalcDamageToEnemy call boundary",
    )
    args = parser.parse_args()

    retail_rows = read_jsonl(args.retail)
    reference_rows = read_jsonl(args.reference)
    if not retail_rows or retail_rows[0].get("type") != HEADER_KIND:
        raise ValueError("retail trace has no recognized header")
    header = retail_rows[0]
    if header.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("retail trace schema mismatch")
    if header.get("target_executable_sha256") != TARGET_SHA256:
        raise ValueError("retail trace target mismatch")

    retail_frames = [row for row in retail_rows[1:] if row.get("type") == FRAME_KIND]
    player_bullet_frames = args.player_bullet_frames or args.enemy_collisions
    player_bullets = args.player_bullets or player_bullet_frames
    player_shooting = args.player_shooting or player_bullets
    enclosing_player = args.enclosing_player or player_shooting
    fields = COMMON_FIELDS + (ENCLOSING_PLAYER_FIELDS if enclosing_player else ())
    if player_shooting:
        fields += PLAYER_SHOOTING_FIELDS
    compared_fields = fields + (("player_spawn",) if player_bullets else ())
    if player_bullet_frames:
        compared_fields += (
            "player_bullet_update",
            "player_last_enemy_hit_bits",
            "player_bullets_frame",
        )
    if args.enemy_collisions:
        compared_fields += (
            "enemies(raw-bit projection)",
            "player_damage_calls",
            "player_damage_trace_overflow",
        )
    ignored_draw_z_differences = [0]
    report: dict[str, Any] = {
        "type": "zkth06.retail-reference-comparison",
        "schema_version": 1,
        "claim_boundary": (
            "finite differential evidence over the listed projection; not a proof of "
            "whole-state or whole-program equivalence"
        ),
        "target_executable_sha256": TARGET_SHA256,
        "replay_sha256": header.get("replay_sha256", "unknown"),
        "retail_trace_sha256": sha256_file(args.retail),
        "reference_trace_sha256": sha256_file(args.reference),
        "retail_trace_schema_version": header["schema_version"],
        "frame_boundary": header.get("frame_boundary"),
        "frame_boundary_role": header.get("frame_boundary_role"),
        "controller_patch": header.get("controller_patch"),
        "wine_timing_normalization": header.get("wine_timing_normalization"),
        "wine_version": header.get("wine_version"),
        "gdb_version": header.get("gdb_version"),
        "config_sha256": header.get("config_sha256"),
        "comparison_profile": (
            "enemy-collisions"
            if args.enemy_collisions
            else "player-bullet-frames"
            if player_bullet_frames
            else "player-bullets"
            if player_bullets
            else "player-shooting"
            if player_shooting
            else "enclosing-player"
            if enclosing_player
            else "base"
        ),
        "compared_fields": list(compared_fields),
        "retail_x87_control_words": sorted(
            {str(row["x87_control_word"]) for row in retail_frames}
        ),
        "retail_mxcsr_values": sorted({str(row["mxcsr"]) for row in retail_frames}),
        "observed_retail_metrics": {
            "first_game_frame": min(
                (int(row["game_frame"]) for row in retail_frames), default=None
            ),
            "last_game_frame": max(
                (int(row["game_frame"]) for row in retail_frames), default=None
            ),
            "rng_generation_min": min(
                (int(row["rng_generation"]) for row in retail_frames), default=None
            ),
            "rng_generation_max": max(
                (int(row["rng_generation"]) for row in retail_frames), default=None
            ),
            "distinct_input_masks": len({int(row["input"]) for row in retail_frames}),
            "final_score": (
                int(retail_frames[-1]["score"]) if retail_frames else None
            ),
        },
    }
    if player_bullet_frames:
        report["semantic_projection_exclusions"] = [
            {
                "path": DRAW_ONLY_UPDATE_INPUT,
                "observed_differences": 0,
                "reason": (
                    "DrawBulletExplosions writes 0.4 to collided sprite.pos.z after the "
                    "post-calc anchor; UpdatePlayerBullets overwrites all sprite.pos "
                    "components from gameplay position before bounds or ANM can read them"
                ),
            }
        ]
    if len(retail_frames) != len(reference_rows):
        message = f"length mismatch: retail={len(retail_frames)} reference={len(reference_rows)}"
        report.update(
            {
                "status": "mismatch",
                "retail_frames": len(retail_frames),
                "reference_frames": len(reference_rows),
                "first_mismatch": {"kind": "length"},
            }
        )
        if args.report is not None:
            write_report(args.report, report)
        print(message, file=sys.stderr)
        return 1

    for index, (retail, reference) in enumerate(zip(retail_frames, reference_rows)):
        if int(retail.get("index", -1)) != index:
            raise ValueError(f"non-contiguous retail index at row {index}")
        lhs = normalize_retail(retail, fields)
        rhs = normalize_reference(reference, enclosing_player, player_shooting)
        differing = {
            key: {"retail": lhs[key], "reference": rhs[key]}
            for key in lhs
            if lhs[key] != rhs[key]
        }
        if player_bullets:
            nested_difference = first_nested_difference(
                retail.get("player_spawn"), reference.get("player_spawn")
            )
            if nested_difference is not None:
                differing["player_spawn"] = nested_difference
        if player_bullet_frames:
            for nested_field in (
                "player_bullet_update",
                "player_last_enemy_hit_bits",
                "player_bullets_frame",
            ):
                retail_nested = retail.get(nested_field)
                reference_nested = reference.get(nested_field)
                nested_difference = first_nested_difference(
                    retail_nested,
                    reference_nested,
                    nested_field,
                    ignore_leaf=(
                        draw_only_update_input_filter(retail_nested, reference_nested)
                        if nested_field == "player_bullet_update"
                        else None
                    ),
                    ignored_count=ignored_draw_z_differences,
                )
                if nested_difference is not None:
                    differing[nested_field] = nested_difference
        if args.enemy_collisions:
            retail_enemies = [
                {key: value for key, value in enemy.items() if key not in ("x", "y")}
                for enemy in retail.get("enemies", [])
            ]
            reference_enemies = [
                {key: value for key, value in enemy.items() if key not in ("x", "y")}
                for enemy in reference.get("enemies", [])
            ]
            for nested_field, retail_nested, reference_nested in (
                ("enemies", retail_enemies, reference_enemies),
                (
                    "player_damage_calls",
                    retail.get("player_damage_calls"),
                    reference.get("player_damage_calls"),
                ),
                (
                    "player_damage_trace_overflow",
                    retail.get("player_damage_trace_overflow"),
                    reference.get("player_damage_trace_overflow"),
                ),
            ):
                nested_difference = first_nested_difference(
                    retail_nested, reference_nested, nested_field
                )
                if nested_difference is not None:
                    differing[nested_field] = nested_difference
        if differing:
            if player_bullet_frames:
                report["semantic_projection_exclusions"][0]["observed_differences"] = (
                    ignored_draw_z_differences[0]
                )
            mismatch = {
                "first_mismatch_index": index,
                "retail_frame": retail.get("game_frame"),
                "reference_tick": reference.get("tick"),
                "differing_fields": differing,
            }
            report.update(
                {
                    "status": "mismatch",
                    "compared_frames": index + 1,
                    "first_mismatch": mismatch,
                }
            )
            if args.report is not None:
                write_report(args.report, report)
            print(json.dumps(mismatch, indent=2, sort_keys=True))
            return 1

    report.update(
        {
            "status": "match",
            "compared_frames": len(retail_frames),
            "first_mismatch": None,
        }
    )
    if player_bullet_frames:
        report["semantic_projection_exclusions"][0]["observed_differences"] = (
            ignored_draw_z_differences[0]
        )
    if args.enemy_collisions:
        all_damage_calls = [
            call for frame in retail_frames for call in frame.get("player_damage_calls", [])
        ]
        damaging_frames = [
            int(frame["game_frame"])
            for frame in retail_frames
            if any(int(call["damage"]) != 0 for call in frame.get("player_damage_calls", []))
        ]
        report["observed_enemy_collision_metrics"] = {
            "damage_calls": len(all_damage_calls),
            "damaging_calls": sum(int(call["damage"]) != 0 for call in all_damage_calls),
            "first_damaging_game_frame": damaging_frames[0] if damaging_frames else None,
            "maximum_active_enemies": max(
                (len(frame.get("enemies", [])) for frame in retail_frames), default=0
            ),
            "trace_overflow_frames": sum(
                bool(frame.get("player_damage_trace_overflow")) for frame in retail_frames
            ),
        }
    if args.report is not None:
        write_report(args.report, report)
    print(f"matched {len(retail_frames)} retail/reference anchor frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

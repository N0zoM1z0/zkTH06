#!/usr/bin/env python3
"""Compare a retail GDB anchor trace with the Linux reference JSON trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


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
    enclosing_player = args.enclosing_player or args.player_shooting
    fields = COMMON_FIELDS + (ENCLOSING_PLAYER_FIELDS if enclosing_player else ())
    if args.player_shooting:
        fields += PLAYER_SHOOTING_FIELDS
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
            "player-shooting"
            if args.player_shooting
            else "enclosing-player"
            if enclosing_player
            else "base"
        ),
        "compared_fields": list(fields),
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
        rhs = normalize_reference(reference, enclosing_player, args.player_shooting)
        differing = {
            key: {"retail": lhs[key], "reference": rhs[key]}
            for key in lhs
            if lhs[key] != rhs[key]
        }
        if differing:
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
    if args.report is not None:
        write_report(args.report, report)
    print(f"matched {len(retail_frames)} retail/reference anchor frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Measure collected point-item y inputs in a debug Linux reference runner."""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import arithmetic_obligations
import verify_game_data


MARKER = "ZKTH06_ITEM_Y"
MARKER_RE = re.compile(rf"{MARKER} ([0-9a-fA-F]{{8}})")
CANDIDATE_LOWER_BOUND = -4.0
CANDIDATE_UPPER_BOUND = 452.0
BREAKPOINT_ANCHORS = {
    210: "calculatePointScore(curItem, 100000, 60000, 100)",
    214: "calculatePointScore(curItem, 150000, 100000, 180)",
    218: "calculatePointScore(curItem, 200000, 150000, 270)",
    222: "calculatePointScore(curItem, 300000, 200000, 400)",
}


class ProbeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_anchors(source: Path) -> None:
    lines = source.read_text().splitlines()
    for line_number, anchor in BREAKPOINT_ANCHORS.items():
        if line_number > len(lines) or anchor not in lines[line_number - 1]:
            raise ProbeError(f"source anchor mismatch at {source}:{line_number}")


def gdb_commands(source: Path, data_directory: Path) -> str:
    if "\n" in str(source) or "\n" in str(data_directory):
        raise ProbeError("newline in a GDB path is unsupported")
    lines = [
        "set pagination off",
        "set confirm off",
        f"set cwd {data_directory}",
    ]
    for number, line_number in enumerate(BREAKPOINT_ANCHORS, start=1):
        lines += [
            f"break {source}:{line_number}",
            f"commands {number}",
            "  silent",
            (
                f'  printf "{MARKER} %08x\\n", '
                "*(unsigned int *)&curItem->currentPosition.y"
            ),
            "  continue",
            "end",
        ]
    lines.append("run")
    return "\n".join(lines) + "\n"


def parse_markers(output: str) -> list[int]:
    return [int(match.group(1), 16) for match in MARKER_RE.finditer(output)]


def float32_from_bits(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def summarize(bits_values: list[int]) -> dict[str, Any]:
    values = [float32_from_bits(bits) for bits in bits_values]
    finite = [value for value in values if math.isfinite(value)]
    exceptional = len(values) - len(finite)
    outside = sum(
        not (CANDIDATE_LOWER_BOUND <= value <= CANDIDATE_UPPER_BOUND)
        for value in finite
    )
    truncated = [math.trunc(value) for value in finite]
    return {
        "collections": len(values),
        "finite": len(finite),
        "exceptional": exceptional,
        "outside_candidate_bound": outside,
        "minimum": None if not finite else min(finite),
        "maximum": None if not finite else max(finite),
        "truncated_minimum": None if not truncated else min(truncated),
        "truncated_maximum": None if not truncated else max(truncated),
        "top_branch": sum(value < 128 for value in truncated),
        "position_branch": sum(value >= 128 for value in truncated),
    }


def run_replay(
    gdb: str,
    runner: Path,
    source: Path,
    data_directory: Path,
    replay: Path,
    max_ticks: int,
    timeout: int,
) -> tuple[list[int], str]:
    commands = gdb_commands(source, data_directory)
    with tempfile.NamedTemporaryFile("w", prefix="zkth06-item-score-", suffix=".gdb") as script:
        script.write(commands)
        script.flush()
        completed = subprocess.run(
            [
                gdb,
                "-nx",
                "-q",
                "-batch",
                "-x",
                script.name,
                "--args",
                str(runner),
                "--headless",
                "--replay",
                str(replay),
                "--max-ticks",
                str(max_ticks),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    if completed.returncode != 0:
        raise ProbeError(
            f"GDB/reference run failed for {replay} with status {completed.returncode}:\n"
            f"{completed.stdout[-4000:]}"
        )
    markers = parse_markers(completed.stdout)
    if not markers:
        raise ProbeError(
            f"no point-item breakpoint was observed for {replay}; verify debug symbols, "
            "source correspondence, and replay coverage"
        )
    return markers, completed.stdout


def positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("reference/src/ItemManager.cpp"))
    parser.add_argument("--data-directory", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("data/manifest.json"))
    parser.add_argument("--max-ticks", type=positive, default=200000)
    parser.add_argument("--timeout", type=positive, default=120)
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    parser.add_argument("replays", type=Path, nargs="+")
    args = parser.parse_args()

    gdb = shutil.which("gdb")
    if gdb is None:
        raise ProbeError("gdb is required")
    runner = args.runner.resolve()
    source = args.source.resolve()
    data_directory = args.data_directory.resolve()
    data_manifest = args.data_manifest.resolve()
    replays = [replay.resolve() for replay in args.replays]
    for path in [runner, source, data_directory, data_manifest, *replays]:
        if not path.exists():
            raise ProbeError(f"missing input: {path}")
    verify_source_anchors(source)
    _, valid_data = verify_game_data.verify(data_directory, data_manifest)
    if not valid_data:
        raise ProbeError("runtime data does not match the pinned manifest")

    gdb_version = subprocess.run(
        [gdb, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.splitlines()[0]
    rows = []
    all_bits: list[int] = []
    for replay in replays:
        bits_values, _ = run_replay(
            gdb,
            runner,
            source,
            data_directory,
            replay,
            args.max_ticks,
            args.timeout,
        )
        all_bits.extend(bits_values)
        rows.append(
            {
                "replay": replay.name,
                "replay_sha256": sha256_file(replay),
                **summarize(bits_values),
            }
        )

    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "zkth06.item-score-corpus-probe",
        "generator": {
            "path": "tools/run_item_score_probe.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "evidence_status": (
            "Linux reconstruction debug-breakpoint counterexample search; not original-binary "
            "equivalence, reachability proof, or source/binary correspondence"
        ),
        "gdb": gdb_version,
        "runner_sha256": sha256_file(runner),
        "item_manager_source_sha256": sha256_file(source),
        "runtime_data": {
            "manifest_sha256": sha256_file(data_manifest),
            "required_files_verified": True,
            "optional_config_present": (data_directory / "東方紅魔郷.cfg").is_file(),
            "optional_score_present": (data_directory / "score.dat").is_file(),
        },
        "max_ticks": args.max_ticks,
        "candidate_collection_bound": [CANDIDATE_LOWER_BOUND, CANDIDATE_UPPER_BOUND],
        "replays": rows,
        "total": summarize(all_bits),
    }
    report = arithmetic_obligations.seal(report)
    output = arithmetic_obligations.render(report)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale item-score corpus report: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current item-score corpus report: {args.check}")
    elif args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({report['artifact_sha256']})")
    else:
        sys.stdout.write(output)
    total = report["total"]
    if total["exceptional"] or total["outside_candidate_bound"]:
        print("candidate item-y invariant falsified by the measured corpus", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, subprocess.TimeoutExpired) as error:
        print(f"item-score probe failed: {error}", file=sys.stderr)
        raise SystemExit(1)

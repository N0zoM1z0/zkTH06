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
        "effective_rate_bits": 0x3F800000,
        "player": {
            "x_bits": 0x43400000,
            "y_bits": 0x43C00000,
            "z_bits": 0x3EFAE148,
            "state": 3,
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


def run_comparator(retail: Path, reference: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(COMPARATOR), str(retail), str(reference), "--report", str(report)],
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
    assert len(committed_evidence["compared_fields"]) == 23
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

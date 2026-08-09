#!/usr/bin/env python3
"""Validate the tracked Linux point-item corpus counterexample-search report."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import run_item_score_probe as probe  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "item-score-corpus-v1.json"
EXPECTED_ARTIFACT_SHA256 = "255e22f7aad315400c849a5a60ae54f360e52b127ae5ca010927a1e9bf96a176"
EXPECTED_REPLAYS = {
    "th6_ud000134.rpy": ("7a0de1f12d20b66678f382de1354ab2ee6a0f6ae719e51f06b6c3d6ec01a6ebc", 403),
    "th6_ud000232.rpy": ("22e03aca353d140e268ca962f3934b5e1b67f74d1c654b876c56c224abea8e24", 304),
    "th6_ud002677.rpy": ("01bc11b9226932bddeeeff675f1741b89b129f4c8820b3b1cf185a1cb19ad10f", 599),
    "th6_udLuRB.rpy": ("9132cbb204a8e413e4d48c4976abba00d625cdbd970a402de85c935f20ae7582", 775),
}


def main() -> int:
    artifact_text = ARTIFACT.read_text()
    assert "/home/" not in artifact_text
    assert "local/original-th06" not in artifact_text
    document = json.loads(artifact_text)
    assert document["schema_version"] == 1
    assert document["kind"] == "zkth06.item-score-corpus-probe"
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["generator"]["sha256"] == probe.sha256_file(
        ROOT / "tools" / "run_item_score_probe.py"
    )
    assert document["runtime_data"]["manifest_sha256"] == probe.sha256_file(
        ROOT / "data" / "manifest.json"
    )
    assert document["runtime_data"]["required_files_verified"] is True
    assert document["candidate_collection_bound"] == [-4.0, 452.0]
    assert {
        row["replay"]: (row["replay_sha256"], row["collections"])
        for row in document["replays"]
    } == EXPECTED_REPLAYS
    assert all(row["finite"] == row["collections"] for row in document["replays"])
    assert all(row["exceptional"] == 0 for row in document["replays"])
    assert all(row["outside_candidate_bound"] == 0 for row in document["replays"])
    assert document["total"] == {
        "collections": 2081,
        "finite": 2081,
        "exceptional": 0,
        "outside_candidate_bound": 0,
        "minimum": 11.879809379577637,
        "maximum": 442.97601318359375,
        "truncated_minimum": 11,
        "truncated_maximum": 442,
        "top_branch": 1413,
        "position_branch": 668,
    }
    assert "not original-binary equivalence" in document["evidence_status"]
    print("validated 2,081 measured point-item collections and explicit evidence boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate conservative source candidates for every mapped __ftol2 call."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import ftol2_source_candidates as candidates  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "ftol2-source-candidates-v1.json"
LEDGER = ROOT / "arithmetic" / "obligations-v1.json"
EXPECTED_ARTIFACT_SHA256 = "2885d3ed814784f4446a8f977646b3f1fc2edbdd058285ec37eb77d089a16466"


def main() -> int:
    document = json.loads(ARTIFACT.read_text())
    ledger = json.loads(LEDGER.read_text())
    assert document["schema_version"] == candidates.SCHEMA_VERSION
    assert document["kind"] == candidates.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["base_ledger_artifact_sha256"] == ledger["artifact_sha256"]
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "ftol2_source_candidates.py"
    )
    assert document["upstream"]["url"] == candidates.UPSTREAM_URL
    assert document["upstream"]["revision"] == candidates.UPSTREAM_REVISION
    assert len(document["upstream"]["source_files"]) == 16

    sites = document["sites"]
    base_sites = ledger["sites"]["ftol2_calls"]
    assert len(sites) == len(base_sites) == 77
    assert [site["call_address"] for site in sites] == sorted(
        site["call_address"] for site in sites
    )
    assert {site["call_address"] for site in sites} == {
        site["call_address"] for site in base_sites
    }
    base_by_address = {site["call_address"]: site for site in base_sites}
    assert all(
        site["function"] == base_by_address[site["call_address"]]["function"]
        and site["base_obligation_id"] == base_by_address[site["call_address"]]["id"]
        for site in sites
    )
    assert all(site["correspondence_status"] == candidates.CORRESPONDENCE_STATUS for site in sites)
    assert all(site["proof_status"] == "unproved" for site in sites)
    assert Counter(site["candidate_disposition"] for site in sites) == {
        "omit-after-noninterference": 68,
        "retain": 9,
    }
    assert {
        site["call_address"]
        for site in sites
        if site["candidate_disposition"] == "retain"
    } == {
        "0x0040b38b",
        "0x0041fb14",
        "0x0041fb35",
        "0x0041fb91",
        "0x0041fbb2",
        "0x0041fc11",
        "0x0041fc32",
        "0x0041fc8e",
        "0x0041fcaf",
    }
    assert Counter(site["semantic_sink"] for site in sites) == {
        "audio-fade-duration": 2,
        "audio-volume": 4,
        "bullet-render-selection": 1,
        "d3d-viewport": 28,
        "ecl-variable-dispatch": 1,
        "ending-draw-rectangle": 2,
        "point-item-score": 8,
        "presentation-alpha": 9,
        "presentation-color": 2,
        "text-raster-coordinate": 20,
    }
    assert all(site["source_candidate"]["line"] > 0 for site in sites)
    assert all("\n" not in site["source_candidate"]["line_anchor"] for site in sites)
    assert all(
        site["source_candidate"]["file"] in document["upstream"]["source_files"]
        for site in sites
    )
    assert document["counts"]["sites"] == len(sites)
    assert document["counts"]["candidate_dispositions"] == {
        "omit-after-noninterference": 68,
        "retain": 9,
    }
    print("validated 77 unproved __ftol2 source/slice candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

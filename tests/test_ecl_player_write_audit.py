#!/usr/bin/env python3
"""Validate the proprietary-byte-free fixed-data ECL player-write audit."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations  # noqa: E402
import ecl_player_write_audit as audit  # noqa: E402


ARTIFACT = ROOT / "arithmetic" / "ecl-player-write-v1.json"
DISPATCH_AUDIT = ROOT / "arithmetic" / "ecl-var-dispatch-v1.json"
EXPECTED_ARTIFACT_SHA256 = "cd1d73507c72963dd783dda83c398f741d0cab6e2b5fe4e348e47ad995e06a24"

EXPECTED_FILE_COUNTS = {
    "ecldata1.ecl": (24562, 24, 644, 103, 0),
    "ecldata2.ecl": (26880, 33, 565, 110, 0),
    "ecldata3.ecl": (33070, 35, 838, 203, 7),
    "ecldata4.ecl": (60796, 61, 1969, 301, 24),
    "ecldata5.ecl": (30392, 52, 972, 195, 3),
    "ecldata6.ecl": (30866, 46, 1158, 250, 11),
    "ecldata7.ecl": (59890, 70, 2238, 682, 35),
}


def synthetic_ecl(opcode: int, destination: int) -> bytes:
    sub_offset = 4 + 4 * 4
    instruction = struct.pack("<IHHHHi", 0, opcode, 16, 0xFF00, 0, destination)
    sentinel = struct.pack("<IHHHH", 0xFFFFFFFF, 0xFFFF, 12, 0xFF00, 0x00FF)
    return struct.pack("<HHIIII", 1, 0, 0, 0, 0, sub_offset) + instruction + sentinel


def reject_private_payload(value: Any) -> None:
    if isinstance(value, dict):
        assert "operands" not in value
        assert "raw_bytes" not in value
        for child in value.values():
            reject_private_payload(child)
    elif isinstance(value, list):
        for child in value:
            reject_private_payload(child)


def main() -> int:
    safe_row, _, _, safe_unchecked = audit.parse_ecl(
        "synthetic-safe.ecl", synthetic_ecl(18, -10012)
    )
    assert safe_row["unchecked_output_count"] == 1
    assert safe_row["player_position_output_count"] == 0
    assert safe_unchecked == {-10012: 1}
    hazard_row, _, _, _ = audit.parse_ecl(
        "synthetic-hazard.ecl", synthetic_ecl(18, audit.PLAYER_Y_ID)
    )
    assert hazard_row["player_position_output_count"] == 1

    artifact_text = ARTIFACT.read_text()
    assert "/home/" not in artifact_text
    assert "local/original-th06" not in artifact_text
    document = json.loads(artifact_text)
    dispatch = json.loads(DISPATCH_AUDIT.read_text())

    assert document["schema_version"] == audit.SCHEMA_VERSION
    assert document["kind"] == audit.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert arithmetic_obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["inputs"] == {
        "executable_sha256": arithmetic_obligations.PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": arithmetic_obligations.PINNED_MAPPING_SHA256,
        "data_manifest_sha256": audit.DATA_MANIFEST_SHA256,
        "stage_archive_sha256": audit.STAGE_ARCHIVE_SHA256,
        "ecl_var_dispatch_artifact_sha256": dispatch["artifact_sha256"],
    }
    assert document["generator"]["sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "ecl_player_write_audit.py"
    )
    assert document["generator"]["x87_audit_sha256"] == arithmetic_obligations.sha256_file(
        ROOT / "tools" / "x87_audit.py"
    )
    assert document["extractor"]["revision"] == audit.THTK_REVISION
    assert document["extractor"]["version"] == audit.THTK_VERSION
    assert len(document["extractor"]["selected_source_files"]) == 8
    assert document["upstream"]["revision"] == audit.UPSTREAM_REVISION

    assert document["counts"] == {
        "ecl_files": 7,
        "subroutines": 321,
        "subroutine_instructions": 8384,
        "candidate_outputs": 1844,
        "guarded_outputs": 1764,
        "unchecked_outputs": 80,
        "checked_instruction_roles": 28,
        "source_anchors": 17,
    }
    assert len(document["checked_instruction_roles"]) == len(audit.EXPECTED_INSTRUCTIONS) == 28
    assert [int(row["address"], 16) for row in document["checked_instruction_roles"]] == list(
        audit.EXPECTED_INSTRUCTIONS
    )

    files = {row["name"]: row for row in document["ecl_files"]}
    assert set(files) == set(audit.ECL_FILES)
    for name, expected in EXPECTED_FILE_COUNTS.items():
        row = files[name]
        assert row["sha256"] == audit.EXPECTED_ECL_SHA256[name]
        assert (
            row["size"],
            row["subroutine_count"],
            row["subroutine_instruction_count"],
            row["candidate_output_count"],
            row["unchecked_output_count"],
        ) == expected
        assert row["sentinel_count"] == row["subroutine_count"]
        assert row["readonly_output_count"] == 0
        assert row["player_position_output_count"] == 0

    contract = document["fixed_data_contract"]
    assert contract["candidate_output_opcodes"] == list(range(3, 27))
    assert contract["guarded_output_opcodes"] == list(audit.GUARDED_OUTPUT_OPCODES)
    assert contract["unchecked_output_opcodes"] == [18, 19]
    assert contract["player_position_ids"] == [-10018, -10019, -10020]
    assert contract["player_y_id"] == -10019
    assert contract["player_position_output_count"] == 0
    assert contract["unchecked_readonly_output_count"] == 0
    assert contract["unchecked_destination_counts"] == [
        {"value": -10012, "count": 61},
        {"value": -10004, "count": 2},
        {"value": -10002, "count": 1},
        {"value": -10001, "count": 16},
    ]
    assert contract["lean_contracts"]["fixed_support"].endswith(
        "retail_unchecked_support_excludes_player_position"
    )

    writer_dispatch = {row["opcode"]: row for row in document["writer_dispatch"]}
    assert set(writer_dispatch) == set(range(3, 27))
    assert writer_dispatch[18] == {
        "opcode": 18,
        "handler_target": "0x00407847",
        "modeled_policy": "unchecked-direct",
    }
    assert writer_dispatch[19] == {
        "opcode": 19,
        "handler_target": "0x00407871",
        "modeled_policy": "unchecked-direct",
    }
    assert len(document["open_obligations"]) == 6
    reject_private_payload(document)
    print("validated 8,384 fixed ECL instructions and zero player-position outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

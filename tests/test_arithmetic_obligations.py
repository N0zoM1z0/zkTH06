#!/usr/bin/env python3
"""Validate the tracked, proprietary-byte-free arithmetic obligation ledger."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arithmetic_obligations as obligations  # noqa: E402


LEDGER = ROOT / "arithmetic" / "obligations-v1.json"
EXPECTED_ARTIFACT_SHA256 = "1c4c128284bf5ab4aa36e636cd5ed15f0300e5295e7fb29f12c0cb2f897f65af"


def reject_disassembly_operands(value: Any) -> None:
    if isinstance(value, dict):
        assert "operands" not in value
        for child in value.values():
            reject_disassembly_operands(child)
    elif isinstance(value, list):
        for child in value:
            reject_disassembly_operands(child)


def main() -> int:
    ledger_text = LEDGER.read_text()
    assert "/home/" not in ledger_text
    assert "local/original-th06" not in ledger_text
    document = json.loads(ledger_text)
    assert document["schema_version"] == obligations.SCHEMA_VERSION
    assert document["kind"] == obligations.KIND
    assert document["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert obligations.document_digest(document) == EXPECTED_ARTIFACT_SHA256
    assert document["generator"]["sha256"] == obligations.sha256_file(
        ROOT / "tools" / "arithmetic_obligations.py"
    )
    assert document["generator"]["x87_audit_sha256"] == obligations.sha256_file(
        ROOT / "tools" / "x87_audit.py"
    )
    assert document["target"] == {
        "title": "Touhou Koumakyou 1.02h Japanese",
        "executable_sha256": obligations.PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": obligations.PINNED_MAPPING_SHA256,
        "implemented_sha256": obligations.PINNED_IMPLEMENTED_SHA256,
    }
    assert document["model_contracts"]["comparison_relation_order"] == [
        "greater",
        "less",
        "equal",
        "unordered",
    ]
    assert document["model_contracts"]["comparison_consumers"] == (
        obligations.SIGNATURE_MODELS
    )

    comparisons = document["sites"]["comparisons"]
    assert len(comparisons) == 244
    assert [site["address"] for site in comparisons] == sorted(
        site["address"] for site in comparisons
    )
    assert len({site["id"] for site in comparisons}) == 244
    assert all(site["class"] == "x87-fcomp-status-branch-v1" for site in comparisons)
    assert all(site["instruction"] == "fcomp" for site in comparisons)
    assert all(site["slice_disposition"] == "unclassified" for site in comparisons)
    assert Counter(site["operand_width"] for site in comparisons) == {
        "dword": 236,
        "qword": 8,
    }
    assert Counter(site["consumer_signature"] for site in comparisons) == {
        "fnstsw ax; and eax,0x100; je": 1,
        "fnstsw ax; and eax,0x100; jne": 32,
        "fnstsw ax; and eax,0x4100; je": 18,
        "fnstsw ax; and eax,0x4100; jne": 22,
        "fnstsw ax; test ah,0x1; jne": 13,
        "fnstsw ax; test ah,0x41; jne": 7,
        "fnstsw ax; test ah,0x41; jp": 38,
        "fnstsw ax; test ah,0x44; jnp": 11,
        "fnstsw ax; test ah,0x44; jp": 18,
        "fnstsw ax; test ah,0x5; jnp": 16,
        "fnstsw ax; test ah,0x5; jp": 68,
    }

    ftol2_sites = document["sites"]["ftol2_calls"]
    assert len(ftol2_sites) == 77
    assert [site["call_address"] for site in ftol2_sites] == sorted(
        site["call_address"] for site in ftol2_sites
    )
    assert len({site["id"] for site in ftol2_sites}) == 77
    assert all(site["class"] == "x87-ftol2-low-result-v1" for site in ftol2_sites)
    assert all(site["slice_disposition"] == "unclassified" for site in ftol2_sites)
    assert all(site["reachable_signed_i32_range"] == "unproved" for site in ftol2_sites)
    assert Counter(site["predecessor"]["mnemonic"] for site in ftol2_sites) == {
        "fadd": 2,
        "fdiv": 4,
        "fld": 60,
        "fmul": 7,
        "fsubp": 2,
        "fsubr": 2,
    }
    assert Counter(
        site["bounded_result_observation"]["eax_observed_mask"]
        for site in ftol2_sites
    ) == {"0x000000ff": 2, "0xffffffff": 75}
    assert all(
        site["bounded_result_observation"]["edx_observed_mask"] == "0x00000000"
        for site in ftol2_sites
    )
    assert Counter(
        site["bounded_result_observation"]["termination"] for site in ftol2_sites
    ) == {"control-flow-boundary": 15, "resolved": 28, "subsequent-call": 34}
    assert {
        site["id"]
        for site in ftol2_sites
        if site["bounded_result_observation"]["eax_observed_mask"] == "0x000000ff"
    } == {"ftol2-00403f4c", "ftol2-00416fbc"}

    assert document["counts"]["comparison_sites"] == len(comparisons)
    assert document["counts"]["ftol2_sites"] == len(ftol2_sites)
    assert document["counts"]["ftol2_edx_observed_sites"] == 0
    reject_disassembly_operands(document)
    print(
        "validated 244 comparison and 77 __ftol2 address-level arithmetic obligations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

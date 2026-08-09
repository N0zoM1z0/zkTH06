#!/usr/bin/env python3
"""Generate a path-free address ledger for pinned TH06 arithmetic obligations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.arithmetic-obligations"
PINNED_EXECUTABLE_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
PINNED_MAPPING_SHA256 = "0f20300d5b107b36c933a7f7dc448407ee5f01c5cd7faad132d406c023163191"
PINNED_IMPLEMENTED_SHA256 = "07b448de3503a285f3464f618c7c384607050c0fff81e0642aa13968fcb61311"
FTOL2_ADDRESS = "0x0045ba78"
FTOL2_SIZE = 117
FTOL2_SHA256 = "5333b186c02836974c6f792303aeb2c00d856316b93ccbbe65f51def6ae661b4"
SOFTFLOAT_PROBE_SHA256 = "b062a031b5866b7e86514db17d162ecbdf9398b0a5d0c5530dfcf6c4889ffe71"

RELATION_ORDER = ["greater", "less", "equal", "unordered"]
SIGNATURE_MODELS: dict[str, dict[str, Any]] = {
    "fnstsw ax; and eax,0x100; je": {
        "filter": "andEax100",
        "branch": "je",
        "truth_table": [True, False, True, False],
        "lean_theorem": "ZkTH06.X87Compare.and_100_je_table",
    },
    "fnstsw ax; and eax,0x100; jne": {
        "filter": "andEax100",
        "branch": "jne",
        "truth_table": [False, True, False, True],
        "lean_theorem": "ZkTH06.X87Compare.and_100_jne_table",
    },
    "fnstsw ax; and eax,0x4100; je": {
        "filter": "andEax4100",
        "branch": "je",
        "truth_table": [True, False, False, False],
        "lean_theorem": "ZkTH06.X87Compare.and_4100_je_table",
    },
    "fnstsw ax; and eax,0x4100; jne": {
        "filter": "andEax4100",
        "branch": "jne",
        "truth_table": [False, True, True, True],
        "lean_theorem": "ZkTH06.X87Compare.and_4100_jne_table",
    },
    "fnstsw ax; test ah,0x1; jne": {
        "filter": "testAh1",
        "branch": "jne",
        "truth_table": [False, True, False, True],
        "lean_theorem": "ZkTH06.X87Compare.test_1_jne_table",
    },
    "fnstsw ax; test ah,0x41; jne": {
        "filter": "testAh41",
        "branch": "jne",
        "truth_table": [False, True, True, True],
        "lean_theorem": "ZkTH06.X87Compare.test_41_jne_table",
    },
    "fnstsw ax; test ah,0x41; jp": {
        "filter": "testAh41",
        "branch": "jp",
        "truth_table": [True, False, False, True],
        "lean_theorem": "ZkTH06.X87Compare.test_41_jp_table",
    },
    "fnstsw ax; test ah,0x44; jnp": {
        "filter": "testAh44",
        "branch": "jnp",
        "truth_table": [False, False, True, False],
        "lean_theorem": "ZkTH06.X87Compare.test_44_jnp_table",
    },
    "fnstsw ax; test ah,0x44; jp": {
        "filter": "testAh44",
        "branch": "jp",
        "truth_table": [True, True, False, True],
        "lean_theorem": "ZkTH06.X87Compare.test_44_jp_table",
    },
    "fnstsw ax; test ah,0x5; jnp": {
        "filter": "testAh5",
        "branch": "jnp",
        "truth_table": [False, True, False, False],
        "lean_theorem": "ZkTH06.X87Compare.test_5_jnp_table",
    },
    "fnstsw ax; test ah,0x5; jp": {
        "filter": "testAh5",
        "branch": "jp",
        "truth_table": [True, False, True, True],
        "lean_theorem": "ZkTH06.X87Compare.test_5_jp_table",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def document_digest(document: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in document.items() if key != "artifact_sha256"}
    return hashlib.sha256(canonical_bytes(unsigned)).hexdigest()


def seal(document: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(document)
    sealed["artifact_sha256"] = document_digest(sealed)
    return sealed


def _require_pinned_inputs(summary: dict[str, Any]) -> None:
    expected = {
        "executable_sha256": PINNED_EXECUTABLE_SHA256,
        "mapping_sha256": PINNED_MAPPING_SHA256,
        "implemented_sha256": PINNED_IMPLEMENTED_SHA256,
    }
    for key, expected_hash in expected.items():
        actual = summary["inputs"].get(key)
        if actual != expected_hash:
            raise ValueError(f"{key}: expected {expected_hash}, got {actual}")
    if summary.get("schema_version") != x87_audit.SCHEMA_VERSION:
        raise ValueError(
            "x87 audit schema mismatch: expected "
            f"{x87_audit.SCHEMA_VERSION}, got {summary.get('schema_version')}"
        )


def _comparison_sites(summary: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for site in summary["mapped_th06_functions"]["comparison_sites"]:
        signature = site["consumer_signature"]
        if signature not in SIGNATURE_MODELS:
            raise ValueError(
                f"comparison at {site['address']} has unsupported consumer {signature!r}"
            )
        if site["mnemonic"] != "fcomp" or site["memory_width"] not in {"dword", "qword"}:
            raise ValueError(f"comparison at {site['address']} is outside the modeled forms")
        records.append(
            {
                "id": f"cmp-{site['address'][2:]}",
                "class": "x87-fcomp-status-branch-v1",
                "address": site["address"],
                "function": site["function"],
                "function_offset": site["function_offset"],
                "instruction": "fcomp",
                "operand_width": site["memory_width"],
                "consumer_signature": signature,
                "slice_disposition": "unclassified",
            }
        )
    records.sort(key=lambda record: record["address"])
    if len(records) != 244:
        raise ValueError(f"expected 244 mapped comparison sites, got {len(records)}")
    return records


def _compact_observer(observer: dict[str, Any] | None) -> dict[str, Any] | None:
    if observer is None:
        return None
    return {
        "address": observer["address"],
        "mnemonic": observer["mnemonic"],
        "aliases": observer["aliases"],
    }


def _ftol2_sites(summary: dict[str, Any]) -> list[dict[str, Any]]:
    helpers = summary["direct_x87_helper_calls_from_th06"]["helpers"]
    matches = [helper for helper in helpers if helper["name"] == "__ftol2"]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one __ftol2 helper row, got {len(matches)}")
    helper = matches[0]
    if helper["start"] != FTOL2_ADDRESS:
        raise ValueError(f"unexpected __ftol2 address {helper['start']}")

    records: list[dict[str, Any]] = []
    for site in helper["sites"]:
        observation = site["result_observation"]
        if observation["eax_observed_mask"] == "0x00000000":
            raise ValueError(f"no bounded EAX-family observer after {site['address']}")
        if observation["edx_observed_mask"] != "0x00000000":
            raise ValueError(f"bounded EDX observer found after {site['address']}")
        predecessor = site["predecessor"]
        if predecessor is None:
            raise ValueError(f"missing predecessor at {site['address']}")
        records.append(
            {
                "id": f"ftol2-{site['address'][2:]}",
                "class": "x87-ftol2-low-result-v1",
                "call_address": site["address"],
                "function": site["function"],
                "function_offset": site["function_offset"],
                "predecessor": {
                    "address": predecessor["address"],
                    "mnemonic": predecessor["mnemonic"],
                },
                "bounded_result_observation": {
                    "scan_instruction_limit": observation["scan_instruction_limit"],
                    "eax_observed_mask": observation["eax_observed_mask"],
                    "edx_observed_mask": observation["edx_observed_mask"],
                    "eax_live_mask_at_stop": observation["eax_live_mask_at_stop"],
                    "edx_live_mask_at_stop": observation["edx_live_mask_at_stop"],
                    "first_eax_observer": _compact_observer(
                        observation["first_eax_observer"]
                    ),
                    "first_edx_observer": _compact_observer(
                        observation["first_edx_observer"]
                    ),
                    "termination": observation["termination"],
                    "termination_address": observation["termination_address"],
                },
                "slice_disposition": "unclassified",
                "reachable_signed_i32_range": "unproved",
            }
        )
    records.sort(key=lambda record: record["call_address"])
    if len(records) != 77:
        raise ValueError(f"expected 77 mapped __ftol2 calls, got {len(records)}")
    return records


def build_manifest(summary: dict[str, Any], tool_root: Path) -> dict[str, Any]:
    _require_pinned_inputs(summary)
    comparisons = _comparison_sites(summary)
    ftol2_sites = _ftol2_sites(summary)
    signature_counts = Counter(site["consumer_signature"] for site in comparisons)
    width_counts = Counter(site["operand_width"] for site in comparisons)
    predecessor_counts = Counter(site["predecessor"]["mnemonic"] for site in ftol2_sites)
    eax_mask_counts = Counter(
        site["bounded_result_observation"]["eax_observed_mask"] for site in ftol2_sites
    )
    termination_counts = Counter(
        site["bounded_result_observation"]["termination"] for site in ftol2_sites
    )

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "target": {
            "title": "Touhou Koumakyou 1.02h Japanese",
            "executable_sha256": PINNED_EXECUTABLE_SHA256,
            "mapping_sha256": PINNED_MAPPING_SHA256,
            "implemented_sha256": PINNED_IMPLEMENTED_SHA256,
        },
        "generator": {
            "path": "tools/arithmetic_obligations.py",
            "sha256": sha256_file(tool_root / "arithmetic_obligations.py"),
            "x87_audit_path": "tools/x87_audit.py",
            "x87_audit_sha256": sha256_file(tool_root / "x87_audit.py"),
            "x87_audit_schema_version": x87_audit.SCHEMA_VERSION,
            "disassembler": summary["disassembler"],
        },
        "evidence_levels": {
            "static": (
                "Deterministic decode and bounded syntactic use scan of the pinned image; "
                "not reachability, control-flow-complete data flow, or a decoding proof."
            ),
            "empirical": (
                "Deterministic counterexample search on one recorded host/toolchain; "
                "not universal arithmetic equivalence."
            ),
            "proved_model_fact": (
                "Lean theorem about the stated model only; not yet a binary/source/guest binding."
            ),
            "open": "A premise required by the eventual refinement theorem.",
        },
        "model_contracts": {
            "comparison_relation_order": RELATION_ORDER,
            "comparison_consumers": SIGNATURE_MODELS,
            "ftol2": {
                "projection": "ZkTH06.X87Ftol2.observedLow32",
                "correction_theorem": (
                    "ZkTH06.X87Ftol2.correction_recovers_truncation"
                ),
                "register_theorem": (
                    "ZkTH06.X87Ftol2.high_half_irrelevant_to_observed_projection"
                ),
            },
        },
        "obligation_classes": [
            {
                "id": "x87-fcomp-status-branch-v1",
                "site_count": len(comparisons),
                "evidence": [
                    {
                        "level": "static",
                        "claim": (
                            "Every recorded mapped site decodes as fcomp m32fp/m64fp followed "
                            "immediately by fnstsw AX, an observed mask, and a conditional branch."
                        ),
                    },
                    {
                        "level": "empirical",
                        "claim": (
                            "The pinned SoftFloat probe matched 4,000,220 x87/SoftFloat "
                            "comparison condition/status tuples with zero mismatch."
                        ),
                        "probe_sha256": SOFTFLOAT_PROBE_SHA256,
                    },
                    {
                        "level": "proved_model_fact",
                        "claim": (
                            "Lean evaluates the eleven recorded masks/branches over "
                            "greater, less, equal, and unordered."
                        ),
                        "definition": "ZkTH06.X87Compare.branchTaken",
                    },
                ],
                "open_obligations": [
                    "Prove or translation-validate the pinned bytes and local control flow at each address.",
                    "Bind x87 stack operands, memory widths, condition codes, and exception state to the model.",
                    "Prove the admitted control-word/stack/tag invariant for every reachable site.",
                    "Prove the zk arithmetic gadget implements the modeled relation and exception priority.",
                    "Classify each branch as retained or prove its effect noninterfering with projected state.",
                ],
            },
            {
                "id": "x87-ftol2-low-result-v1",
                "site_count": len(ftol2_sites),
                "evidence": [
                    {
                        "level": "static",
                        "claim": (
                            "Every recorded mapped call has an x87 predecessor and an explicit "
                            "bounded EAX/AL observer; no EDX observer appears before the recorded "
                            "straight-line termination boundary."
                        ),
                    },
                    {
                        "level": "empirical",
                        "claim": (
                            "The exact 117-byte helper matched 1,000,014 canonical finite, "
                            "signed-i64-representable inputs, including full EDX:EAX and stack balance."
                        ),
                        "helper_address": FTOL2_ADDRESS,
                        "helper_size": FTOL2_SIZE,
                        "helper_sha256": FTOL2_SHA256,
                    },
                    {
                        "level": "proved_model_fact",
                        "claim": (
                            "Lean checks the correction-to-truncation cases and low-32-bit projection."
                        ),
                        "definitions": [
                            "ZkTH06.X87Ftol2.correction_recovers_truncation",
                            "ZkTH06.X87Ftol2.high_half_irrelevant_to_observed_projection",
                        ],
                    },
                ],
                "open_obligations": [
                    "Prove or translation-validate that every call reaches the hashed helper body.",
                    "Replace the bounded syntactic scan with control-flow-complete register-use analysis.",
                    "Classify each call as retained or prove it noninterfering with projected state.",
                    "For retained calls, prove every reachable input is finite and truncates to signed i32.",
                    "Bind raw ext80 decoding, x87 stack effects, correction code, and guest conversion semantics.",
                ],
            },
        ],
        "counts": {
            "comparison_sites": len(comparisons),
            "comparison_operand_widths": dict(sorted(width_counts.items())),
            "comparison_consumer_signatures": dict(sorted(signature_counts.items())),
            "ftol2_sites": len(ftol2_sites),
            "ftol2_predecessor_mnemonics": dict(sorted(predecessor_counts.items())),
            "ftol2_eax_observed_masks": dict(sorted(eax_mask_counts.items())),
            "ftol2_edx_observed_sites": sum(
                site["bounded_result_observation"]["edx_observed_mask"] != "0x00000000"
                for site in ftol2_sites
            ),
            "ftol2_scan_terminations": dict(sorted(termination_counts.items())),
        },
        "sites": {
            "comparisons": comparisons,
            "ftol2_calls": ftol2_sites,
        },
    }
    return seal(document)


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="verified Japanese v1.02h PE")
    parser.add_argument("--mapping", type=Path, required=True, help="pinned mapping.csv")
    parser.add_argument("--implemented", type=Path, required=True, help="pinned implemented.csv")
    parser.add_argument("--objdump", default="objdump", help="GNU objdump-compatible executable")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="write the canonical ledger here")
    destination.add_argument(
        "--check", type=Path, help="fail unless this tracked ledger is byte-for-byte current"
    )
    args = parser.parse_args()

    version, disassembly = x87_audit.run_objdump(args.executable, args.objdump)
    functions = x87_audit.load_mapping(args.mapping)
    implemented = x87_audit.load_name_set(args.implemented)
    raw = {
        "schema_version": x87_audit.SCHEMA_VERSION,
        "executable": {
            "path": str(args.executable),
            "sha256": x87_audit.sha256_file(args.executable),
        },
        "mapping": {
            "path": str(args.mapping),
            "sha256": x87_audit.sha256_file(args.mapping),
            "function_count": len(functions),
        },
        "implemented": {
            "path": str(args.implemented),
            "sha256": x87_audit.sha256_file(args.implemented),
            "function_count": len(implemented),
        },
        "disassembler": version,
        "audit": x87_audit.audit(
            instructions=x87_audit.parse_disassembly(disassembly),
            functions=functions,
            implemented=implemented,
        ),
    }
    document = build_manifest(x87_audit.summarize(raw), Path(__file__).resolve().parent)
    output = render(document)

    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale arithmetic obligation ledger: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current arithmetic obligation ledger: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

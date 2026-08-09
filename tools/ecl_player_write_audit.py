#!/usr/bin/env python3
"""Audit fixed retail ECL output operands that could alias player position."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import arithmetic_obligations
import run_ftol2_probe
import x87_audit


SCHEMA_VERSION = 1
KIND = "zkth06.ecl-player-write-audit"

STAGE_ARCHIVE_NAME = "紅魔郷ST.DAT"
STAGE_ARCHIVE_SHA256 = "0f834a35aef2d73b05cffecc830c017dacbcc6f11b9a0611a9da2f3970a112e7"
DATA_MANIFEST_SHA256 = "f59a3fa3981eed369b47aa03fe0c9e0c555f976c422bdaa37108ca2f3f892a4a"
ECL_FILES = tuple(f"ecldata{stage}.ecl" for stage in range(1, 8))
EXPECTED_ECL_SHA256 = {
    "ecldata1.ecl": "9d9a40e9f7e3ab9346d3874438134659cacf9d34f4aff57b96b4be4ea85b99d7",
    "ecldata2.ecl": "aa89aaaf13264d909bbaaa24f2af263ae1a58145ad5cc33fcea5eb9cb920c43e",
    "ecldata3.ecl": "44dfcaa737b7d4b3d1275655627e15a9d5b7710fc75a0885fb39d8c9485056d6",
    "ecldata4.ecl": "92695da99b651da492f4fb7c7497b5c8ed8105a23370cc4529901609077c8b60",
    "ecldata5.ecl": "50b5c4777a56910148466c7e5ea1c8dadc126e706420604d52421a49bf861d1b",
    "ecldata6.ecl": "4a4d4e5bf7ff79ab49b918267130b42308b3a5565cc892dc0e636b8b667740e5",
    "ecldata7.ecl": "fb900c7e54b1f5d0c36a2e09986bef8f8fde002ca7b5005d12e3aaec7e856392",
}

THTK_URL = "https://github.com/thpatch/thtk"
THTK_REVISION = "892114a0fcaa0bbdaaecf3cb4ad56f758683fb40"
THTK_VERSION = "Touhou Toolkit release 12"
THTK_SOURCE_FILES = (
    "thdat/thdat.c",
    "thtk/error.c",
    "thtk/io.c",
    "thtk/thcrypt.c",
    "thtk/thdat.c",
    "thtk/thdat06.c",
    "thtk/thlzss.c",
    "thtk/thrle.c",
)

UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = "cc475a0bc3fef38683b0f02224c87ddba0a021d9"
SOURCE_ANCHORS = (
    ("src/EclManager.hpp", 349, "enum EclRawInstrOpcode", "opcode enumeration"),
    ("src/EclManager.hpp", 354, "ECL_OPCODE_JUMPDEC", "guarded writer opcode 3"),
    ("src/EclManager.hpp", 369, "ECL_OPCODE_MATHINC", "unchecked writer opcode 18"),
    ("src/EclManager.hpp", 370, "ECL_OPCODE_MATHDEC", "unchecked writer opcode 19"),
    ("src/EclManager.cpp", 126, "switch (instruction->opCode)", "subroutine dispatch"),
    ("src/EclManager.cpp", 133, "EnemyEclInstr::SetVar", "jump-decrement guarded store"),
    ("src/EclManager.cpp", 143, "EnemyEclInstr::SetVar", "set opcode guarded store"),
    ("src/EclManager.cpp", 185, "EnemyEclInstr::MathAdd", "typed arithmetic writer"),
    ("src/EclManager.cpp", 188, "EnemyEclInstr::GetVar", "increment pointer resolution"),
    ("src/EclManager.cpp", 189, "*local_3c += 1", "unchecked increment store"),
    ("src/EclManager.cpp", 192, "EnemyEclInstr::GetVar", "decrement pointer resolution"),
    ("src/EclManager.cpp", 193, "*local_40 -= 1", "unchecked decrement store"),
    ("src/EnemyEclInstr.cpp", 197, "case ECL_VAR_PLAYER_POS_Y", "player-y variable ID"),
    ("src/EnemyEclInstr.cpp", 199, "ECL_VALUE_TYPE_READONLY", "player-y readonly type"),
    ("src/EnemyEclInstr.cpp", 200, "g_Player.positionCenter.y", "player-y returned pointer"),
    ("src/EnemyEclInstr.cpp", 261, "lhsType == ECL_VALUE_TYPE_INT", "integer store guard"),
    ("src/EnemyEclInstr.cpp", 265, "lhsType == ECL_VALUE_TYPE_FLOAT", "float store guard"),
)

MAPPED_FUNCTIONS = {
    "th06::EclManager::RunEcl": (0x004074A0, 0x3504),
    "th06::EnemyEclInstr::GetVar": (0x0040AFB0, 0x36C),
    "th06::EnemyEclInstr::SetVar": (0x0040B3C0, 0x58),
}

RUN_ECL_JUMP_TABLE_ADDRESS = 0x0040A9A4
RUN_ECL_JUMP_TABLE_COUNT = 0x87
GUARDED_OUTPUT_OPCODES = tuple(range(3, 18)) + tuple(range(20, 27))
UNCHECKED_OUTPUT_OPCODES = (18, 19)
CANDIDATE_OUTPUT_OPCODES = tuple(range(3, 27))
PLAYER_POSITION_IDS = (-10018, -10019, -10020)
READONLY_IDS = (-10013, -10014, -10018, -10019, -10020, -10021, -10023)
PLAYER_Y_ID = -10019
PLAYER_Y_GETVAR_TARGET = 0x0040B1DB
EXPECTED_UNCHECKED_HANDLER_TARGETS = {18: 0x00407847, 19: 0x00407871}

EXPECTED_INSTRUCTIONS = {
    # RunEcl opcode normalization and table dispatch.
    0x00407515: ("movsx", "eax,WORD PTR [edx+0x4]", "load ECL opcode"),
    0x00407525: ("sub", "ecx,0x1", "normalize opcode one to table index zero"),
    0x0040752E: ("cmp", "DWORD PTR [ebp-0x294],0x86", "bound normalized opcode by 134"),
    0x00407538: ("ja", "0x40a008", "reject opcode outside dispatch table"),
    0x00407544: ("jmp", "DWORD PTR [edx*4+0x40a9a4]", "dispatch through 135-entry table"),
    # Opcode 18 resolves the first data word directly, then writes without a type guard.
    0x0040784C: ("add", "ecx,0xc", "locate increment destination word"),
    0x00407854: ("call", "0x40afb0", "resolve increment destination through GetVar"),
    0x0040785C: ("mov", "DWORD PTR [ebp-0x38],eax", "retain increment destination pointer"),
    0x00407862: ("mov", "ecx,DWORD PTR [eax]", "load increment destination value"),
    0x00407864: ("add", "ecx,0x1", "increment value without checking returned type"),
    0x0040786A: ("mov", "DWORD PTR [edx],ecx", "store unchecked increment result"),
    # Opcode 19 has the corresponding unchecked decrement path.
    0x00407876: ("add", "eax,0xc", "locate decrement destination word"),
    0x0040787E: ("call", "0x40afb0", "resolve decrement destination through GetVar"),
    0x00407886: ("mov", "DWORD PTR [ebp-0x3c],eax", "retain decrement destination pointer"),
    0x0040788C: ("mov", "eax,DWORD PTR [edx]", "load decrement destination value"),
    0x0040788E: ("sub", "eax,0x1", "decrement value without checking returned type"),
    0x00407894: ("mov", "DWORD PTR [ecx],eax", "store unchecked decrement result"),
    # GetVar maps -10019 to player center y and marks it readonly (type 2).
    0x0040B1DB: ("cmp", "DWORD PTR [ebp+0x10],0x0", "test optional player-y type output"),
    0x0040B1E1: ("mov", "edx,DWORD PTR [ebp+0x10]", "load player-y type output pointer"),
    0x0040B1E4: ("mov", "DWORD PTR [edx],0x2", "mark player y readonly"),
    0x0040B1EA: ("mov", "eax,0x6caa6c", "return retail player center-y address"),
    # SetVar writes only type 0 (integer) or type 1 (float), never readonly type 2.
    0x0040B3E7: ("call", "0x40afb0", "resolve SetVar output and its type"),
    0x0040B3F2: ("cmp", "DWORD PTR [ebp-0xc],0x0", "test integer output type"),
    0x0040B3F6: ("jne", "0x40b404", "skip integer store for other types"),
    0x0040B400: ("mov", "DWORD PTR [edx],ecx", "store integer output"),
    0x0040B404: ("cmp", "DWORD PTR [ebp-0xc],0x1", "test float output type"),
    0x0040B408: ("jne", "0x40b414", "skip final store for non-float type"),
    0x0040B412: ("mov", "DWORD PTR [edx],ecx", "store float output bits"),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_sealed(path: Path, label: str) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if arithmetic_obligations.document_digest(document) != document.get("artifact_sha256"):
        raise ValueError(f"{label} has an invalid artifact digest: {path}")
    return document


def pinned_blob(root: Path, revision: str, source_file: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{source_file}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ValueError(
            f"cannot read {source_file} at {revision}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def verify_source_anchors(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blobs: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for source_file, line, anchor, role in SOURCE_ANCHORS:
        if source_file not in blobs:
            blobs[source_file] = pinned_blob(source_root, UPSTREAM_REVISION, source_file)
        lines = blobs[source_file].decode("utf-8").splitlines()
        if line <= 0 or line > len(lines) or anchor not in lines[line - 1]:
            raise ValueError(f"source anchor mismatch at {source_file}:{line}: {anchor!r}")
        rows.append({"file": source_file, "line": line, "anchor": anchor, "role": role})
    hashes = {
        source_file: sha256_bytes(blob) for source_file, blob in sorted(blobs.items())
    }
    return rows, hashes


def verify_thtk_sources(thtk_root: Path) -> dict[str, str]:
    return {
        source_file: sha256_bytes(pinned_blob(thtk_root, THTK_REVISION, source_file))
        for source_file in THTK_SOURCE_FILES
    }


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    raw = manifest_path.read_bytes()
    if sha256_bytes(raw) != DATA_MANIFEST_SHA256:
        raise ValueError("data manifest hash does not match the pinned manifest")
    manifest = json.loads(raw)
    matches = [
        row
        for row in manifest.get("required_files", [])
        if row.get("filename") == STAGE_ARCHIVE_NAME
    ]
    if len(matches) != 1 or matches[0].get("sha256") != STAGE_ARCHIVE_SHA256:
        raise ValueError("data manifest does not bind the pinned stage archive")
    return manifest


def extract_ecl_files(stage_archive: Path, thdat: Path) -> tuple[dict[str, bytes], str]:
    archive = stage_archive.read_bytes()
    if sha256_bytes(archive) != STAGE_ARCHIVE_SHA256:
        raise ValueError("stage archive hash does not match the pinned retail data")
    version = subprocess.run(
        [str(thdat.resolve()), "-V"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    if version != THTK_VERSION:
        raise ValueError(f"unexpected thdat version: {version!r}")
    extracted: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="zkth06-ecl-extract-") as directory:
        subprocess.run(
            [
                str(thdat.resolve()),
                "-x6",
                str(stage_archive.resolve()),
                "-C",
                directory,
                *ECL_FILES,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        actual_names = sorted(path.name for path in Path(directory).iterdir())
        if actual_names != list(ECL_FILES):
            raise ValueError(f"unexpected extracted ECL file set: {actual_names}")
        for name in ECL_FILES:
            data = (Path(directory) / name).read_bytes()
            digest = sha256_bytes(data)
            if digest != EXPECTED_ECL_SHA256[name]:
                raise ValueError(f"extracted {name} has unexpected SHA-256 {digest}")
            extracted[name] = data
    return extracted, version


def destination_for_instruction(opcode: int, data: bytes, position: int, size: int) -> int | None:
    if opcode == 3:
        parameter_offset = position + 12 + 8
    elif 4 <= opcode <= 26:
        parameter_offset = position + 12
    else:
        return None
    if parameter_offset + 4 > position + size:
        raise ValueError(f"opcode {opcode} has no complete output operand")
    return struct.unpack_from("<i", data, parameter_offset)[0]


def histogram(counter: Counter[int]) -> list[dict[str, int]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items())
    ]


def parse_ecl(name: str, data: bytes) -> tuple[dict[str, Any], Counter[int], Counter[int], Counter[int]]:
    if len(data) < 16:
        raise ValueError(f"{name} is shorter than the TH06 ECL header")
    sub_count, timeline_count = struct.unpack_from("<HH", data)
    offset_count = 3 + sub_count
    offset_table_end = 4 + 4 * offset_count
    if offset_table_end > len(data):
        raise ValueError(f"{name} has a truncated offset table")
    offsets = struct.unpack_from(f"<{offset_count}I", data, 4)
    timeline_offsets = offsets[:3]
    sub_offsets = offsets[3:]
    if timeline_count != 0:
        raise ValueError(f"{name} has unexpected TH06 timeline count {timeline_count}")
    if any(offset == 0 for offset in sub_offsets):
        raise ValueError(f"{name} has a null subroutine offset")
    if list(sub_offsets) != sorted(set(sub_offsets)):
        raise ValueError(f"{name} subroutine offsets are not strictly increasing")
    nonzero_offsets = sorted(set(offset for offset in offsets if offset != 0))
    if any(offset < offset_table_end or offset >= len(data) for offset in nonzero_offsets):
        raise ValueError(f"{name} contains an out-of-range section offset")

    opcode_counts: Counter[int] = Counter()
    destination_counts: Counter[int] = Counter()
    unchecked_destinations: Counter[int] = Counter()
    sentinel_count = 0
    for sub_index, start in enumerate(sub_offsets):
        boundary = min(
            (offset for offset in nonzero_offsets if offset > start),
            default=len(data),
        )
        position = start
        while True:
            if position + 12 > boundary:
                raise ValueError(f"{name} sub {sub_index} has a truncated instruction header")
            time, opcode, size, rank_mask, parameter_mask = struct.unpack_from(
                "<IHHHH", data, position
            )
            if time == 0xFFFFFFFF:
                if (opcode, size, rank_mask, parameter_mask) != (
                    0xFFFF,
                    12,
                    0xFF00,
                    0x00FF,
                ):
                    raise ValueError(f"{name} sub {sub_index} has a malformed sentinel")
                position += size
                sentinel_count += 1
                break
            if size < 12 or position + size > boundary:
                raise ValueError(f"{name} sub {sub_index} has invalid instruction size {size}")
            if opcode > RUN_ECL_JUMP_TABLE_COUNT:
                raise ValueError(f"{name} sub {sub_index} has unsupported opcode {opcode}")
            opcode_counts[opcode] += 1
            destination = destination_for_instruction(opcode, data, position, size)
            if destination is not None:
                destination_counts[destination] += 1
                if opcode in UNCHECKED_OUTPUT_OPCODES:
                    unchecked_destinations[destination] += 1
            position += size
        if position != boundary:
            raise ValueError(
                f"{name} sub {sub_index} sentinel ends at {position:#x}, "
                f"expected section boundary {boundary:#x}"
            )
    if sentinel_count != sub_count:
        raise ValueError(f"{name} does not have one sentinel per subroutine")

    player_position_outputs = sum(destination_counts[value] for value in PLAYER_POSITION_IDS)
    readonly_outputs = sum(destination_counts[value] for value in READONLY_IDS)
    row = {
        "name": name,
        "sha256": sha256_bytes(data),
        "size": len(data),
        "subroutine_count": sub_count,
        "sentinel_count": sentinel_count,
        "header_timeline_count": timeline_count,
        "active_timeline_offsets": [
            f"0x{offset:08x}" for offset in timeline_offsets if offset != 0
        ],
        "subroutine_instruction_count": sum(opcode_counts.values()),
        "candidate_output_count": sum(destination_counts.values()),
        "unchecked_output_count": sum(unchecked_destinations.values()),
        "readonly_output_count": readonly_outputs,
        "player_position_output_count": player_position_outputs,
    }
    return row, opcode_counts, destination_counts, unchecked_destinations


def verify_functions(mapping_path: Path) -> list[dict[str, Any]]:
    by_name = {function.name: function for function in x87_audit.load_mapping(mapping_path)}
    rows: list[dict[str, Any]] = []
    for name, expected in MAPPED_FUNCTIONS.items():
        function = by_name.get(name)
        if function is None or (function.start, function.size) != expected:
            got = None if function is None else (function.start, function.size)
            raise ValueError(f"mapping mismatch for {name}: expected {expected}, got {got}")
        rows.append({"name": name, "start": f"0x{function.start:08x}", "size": function.size})
    return rows


def verify_instructions(disassembly: str) -> list[dict[str, str]]:
    instructions = {
        instruction.address: instruction
        for instruction in x87_audit.parse_disassembly(disassembly)
    }
    rows: list[dict[str, str]] = []
    for address, (mnemonic, operands, role) in EXPECTED_INSTRUCTIONS.items():
        instruction = instructions.get(address)
        if instruction is None:
            raise ValueError(f"missing ECL writer instruction at 0x{address:08x}")
        if (instruction.mnemonic, instruction.operands) != (mnemonic, operands):
            raise ValueError(
                f"instruction mismatch at 0x{address:08x}: got "
                f"{instruction.mnemonic} {instruction.operands!r}, expected "
                f"{mnemonic} {operands!r}"
            )
        rows.append({"address": f"0x{address:08x}", "mnemonic": mnemonic, "role": role})
    return rows


def verify_dispatch(
    image: bytes, dispatch_audit: dict[str, Any]
) -> list[dict[str, Any]]:
    if dispatch_audit.get("kind") != "zkth06.ecl-var-dispatch-audit":
        raise ValueError("selected ECL variable-dispatch artifact has the wrong kind")
    player_y_rows = [
        row
        for row in dispatch_audit.get("dispatch_contract", {}).get("jump_table", [])
        if row.get("variable_id") == PLAYER_Y_ID
    ]
    if len(player_y_rows) != 1 or int(player_y_rows[0]["target"], 16) != PLAYER_Y_GETVAR_TARGET:
        raise ValueError("ECL dispatch artifact does not bind the expected player-y target")

    raw = run_ftol2_probe.extract_pe_range(
        image, RUN_ECL_JUMP_TABLE_ADDRESS, RUN_ECL_JUMP_TABLE_COUNT * 4
    )
    targets = [target for (target,) in struct.iter_unpack("<I", raw)]
    rows: list[dict[str, Any]] = []
    for opcode in CANDIDATE_OUTPUT_OPCODES:
        target = targets[opcode - 1]
        if opcode in EXPECTED_UNCHECKED_HANDLER_TARGETS:
            if target != EXPECTED_UNCHECKED_HANDLER_TARGETS[opcode]:
                raise ValueError(f"unexpected unchecked handler target for opcode {opcode}")
            policy = "unchecked-direct"
        else:
            policy = "typed-guard-candidate"
        rows.append(
            {
                "opcode": opcode,
                "handler_target": f"0x{target:08x}",
                "modeled_policy": policy,
            }
        )
    return rows


def build_document(
    executable: Path,
    mapping_path: Path,
    stage_archive: Path,
    manifest_path: Path,
    dispatch_audit: dict[str, Any],
    source_root: Path,
    thdat: Path,
    thtk_root: Path,
    objdump: str,
    tool_path: Path,
) -> dict[str, Any]:
    image = executable.read_bytes()
    executable_hash = sha256_bytes(image)
    mapping_hash = x87_audit.sha256_file(mapping_path)
    if executable_hash != arithmetic_obligations.PINNED_EXECUTABLE_SHA256:
        raise ValueError("executable hash does not match the pinned Japanese v1.02h image")
    if mapping_hash != arithmetic_obligations.PINNED_MAPPING_SHA256:
        raise ValueError("mapping hash does not match the pinned authoritative mapping")
    dispatch_inputs = dispatch_audit.get("inputs", {})
    if (
        dispatch_inputs.get("executable_sha256"),
        dispatch_inputs.get("mapping_sha256"),
    ) != (executable_hash, mapping_hash):
        raise ValueError("ECL dispatch artifact is not bound to the selected target")

    verify_manifest(manifest_path)
    source_anchors, source_hashes = verify_source_anchors(source_root)
    thtk_source_hashes = verify_thtk_sources(thtk_root)
    extracted, thdat_version = extract_ecl_files(stage_archive, thdat)
    disassembler, disassembly = x87_audit.run_objdump(executable, objdump)

    file_rows: list[dict[str, Any]] = []
    total_opcodes: Counter[int] = Counter()
    total_destinations: Counter[int] = Counter()
    total_unchecked: Counter[int] = Counter()
    for name in ECL_FILES:
        row, opcodes, destinations, unchecked = parse_ecl(name, extracted[name])
        file_rows.append(row)
        total_opcodes.update(opcodes)
        total_destinations.update(destinations)
        total_unchecked.update(unchecked)

    if any(total_destinations[value] != 0 for value in PLAYER_POSITION_IDS):
        raise ValueError("fixed retail ECL names a player-position variable as an output")
    if any(total_unchecked[value] != 0 for value in READONLY_IDS):
        raise ValueError("fixed retail ECL uses unchecked increment/decrement on a readonly ID")

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "inputs": {
            "executable_sha256": executable_hash,
            "mapping_sha256": mapping_hash,
            "data_manifest_sha256": DATA_MANIFEST_SHA256,
            "stage_archive_sha256": STAGE_ARCHIVE_SHA256,
            "ecl_var_dispatch_artifact_sha256": dispatch_audit["artifact_sha256"],
        },
        "generator": {
            "path": "tools/ecl_player_write_audit.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
            "x87_audit_sha256": arithmetic_obligations.sha256_file(
                tool_path.parent / "x87_audit.py"
            ),
            "disassembler": disassembler,
        },
        "extractor": {
            "name": "thtk thdat",
            "version": thdat_version,
            "upstream_url": THTK_URL,
            "revision": THTK_REVISION,
            "selected_source_files": thtk_source_hashes,
            "status": "pinned extractor output checked by hash; extraction correctness unproved",
        },
        "upstream": {
            "url": UPSTREAM_URL,
            "revision": UPSTREAM_REVISION,
            "source_files": source_hashes,
            "anchors": source_anchors,
            "correspondence_status": "manual-disassembly-source-alignment-unproved",
        },
        "mapped_functions": verify_functions(mapping_path),
        "checked_instruction_roles": verify_instructions(disassembly),
        "writer_dispatch": verify_dispatch(image, dispatch_audit),
        "ecl_files": file_rows,
        "fixed_data_contract": {
            "parser": "independent TH06 subroutine-header walk; timeline records excluded",
            "candidate_output_opcodes": list(CANDIDATE_OUTPUT_OPCODES),
            "guarded_output_opcodes": list(GUARDED_OUTPUT_OPCODES),
            "unchecked_output_opcodes": list(UNCHECKED_OUTPUT_OPCODES),
            "player_position_ids": list(PLAYER_POSITION_IDS),
            "player_y_id": PLAYER_Y_ID,
            "readonly_ids": list(READONLY_IDS),
            "opcode_counts": histogram(total_opcodes),
            "candidate_destination_counts": histogram(total_destinations),
            "unchecked_destination_counts": histogram(total_unchecked),
            "player_position_output_count": sum(
                total_destinations[value] for value in PLAYER_POSITION_IDS
            ),
            "unchecked_readonly_output_count": sum(
                total_unchecked[value] for value in READONLY_IDS
            ),
            "lean_contracts": {
                "write_policy": "ZkTH06.EclPlayerWrite.writerPolicy",
                "guarded_player_y": "ZkTH06.EclPlayerWrite.typed_writer_cannot_write_player_y",
                "bypass_reduction": "ZkTH06.EclPlayerWrite.player_y_write_requires_unchecked_opcode",
                "fixed_support": "ZkTH06.EclPlayerWrite.retail_unchecked_support_excludes_player_position",
            },
        },
        "evidence_status": (
            "hash-bound fixed-data parsing and exact static signatures; not an archive/runtime "
            "decoder proof, exhaustive handler theorem, compiler correspondence proof, runtime "
            "immutability proof, whole-program writer proof, or guest binding"
        ),
        "open_obligations": [
            "Prove the pinned thdat extraction agrees with the retail PBG3 archive loader.",
            "Prove the independent ECL header/instruction walk agrees with the retail decoder.",
            "Translation-validate RunEcl dispatch, writer classification, GetVar, and type guards.",
            "Prove no runtime mutation can replace an audited opcode or output destination.",
            "Prove no non-ECL direct or aliased path writes player center or grab-box fields.",
            "Prove the zkVM guest refines the fixed-data ECL write contract.",
        ],
        "counts": {
            "ecl_files": len(file_rows),
            "subroutines": sum(row["subroutine_count"] for row in file_rows),
            "subroutine_instructions": sum(
                row["subroutine_instruction_count"] for row in file_rows
            ),
            "candidate_outputs": sum(total_destinations.values()),
            "guarded_outputs": sum(total_destinations.values()) - sum(total_unchecked.values()),
            "unchecked_outputs": sum(total_unchecked.values()),
            "checked_instruction_roles": len(EXPECTED_INSTRUCTIONS),
            "source_anchors": len(source_anchors),
        },
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("stage_archive", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.json"))
    parser.add_argument(
        "--dispatch-audit",
        type=Path,
        default=Path("arithmetic/ecl-var-dispatch-v1.json"),
    )
    parser.add_argument("--source-root", type=Path, default=Path("repos/th06"))
    parser.add_argument("--thdat", type=Path, default=Path("repos/thtk/build/thdat/thdat"))
    parser.add_argument("--thtk-root", type=Path, default=Path("repos/thtk"))
    parser.add_argument("--objdump", default="objdump")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    document = build_document(
        args.executable,
        args.mapping,
        args.stage_archive,
        args.manifest,
        load_sealed(args.dispatch_audit, "ECL variable-dispatch audit"),
        args.source_root,
        args.thdat,
        args.thtk_root,
        args.objdump,
        Path(__file__).resolve(),
    )
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale ECL player-write audit: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current ECL player-write audit: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build conservative source/slice candidates for the 77 mapped __ftol2 calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import arithmetic_obligations


SCHEMA_VERSION = 1
KIND = "zkth06.ftol2-source-candidates"
UPSTREAM_URL = "https://github.com/GensokyoClub/th06"
UPSTREAM_REVISION = "cc475a0bc3fef38683b0f02224c87ddba0a021d9"
CORRESPONDENCE_STATUS = "manual-disassembly-source-alignment-unproved"
PROOF_STATUS = "unproved"


def annotation(
    address: str,
    function: str,
    source_file: str,
    line: int,
    anchor: str,
    semantic_sink: str,
    candidate_disposition: str,
    range_strategy_candidate: str,
    *,
    inlined_at_line: int | None = None,
    inlined_at_anchor: str | None = None,
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "file": source_file,
        "line": line,
        "line_anchor": anchor,
    }
    if inlined_at_line is not None:
        source["inlined_at_line"] = inlined_at_line
        source["inlined_at_anchor"] = inlined_at_anchor
    return {
        "call_address": address,
        "function": function,
        "source_candidate": source,
        "semantic_sink": semantic_sink,
        "candidate_disposition": candidate_disposition,
        "range_strategy_candidate": range_strategy_candidate,
        "correspondence_status": CORRESPONDENCE_STATUS,
        "proof_status": PROOF_STATUS,
    }


def viewport_annotations(
    function: str, source_file: str, addresses: list[str], lines: list[int]
) -> list[dict[str, Any]]:
    components = ["viewport.X", "viewport.Y", "viewport.Width", "viewport.Height"]
    if len(addresses) != 4 or len(lines) != 4:
        raise ValueError("viewport annotation requires four addresses and lines")
    return [
        annotation(
            address,
            function,
            source_file,
            line,
            component,
            "d3d-viewport",
            "omit-after-noninterference",
            "eliminate-with-render-path",
        )
        for address, line, component in zip(addresses, lines, components)
    ]


def text_argument_annotations(
    function: str,
    addresses: list[str],
    source_lines: list[int],
    anchors: list[str],
) -> list[dict[str, Any]]:
    if not (len(addresses) == len(source_lines) == len(anchors)):
        raise ValueError("text argument annotation lengths differ")
    return [
        annotation(
            address,
            function,
            "src/AnmManager.cpp",
            line,
            anchor,
            "text-raster-coordinate",
            "omit-after-noninterference",
            "eliminate-with-text-rasterization",
        )
        for address, line, anchor in zip(addresses, source_lines, anchors)
    ]


def annotations() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows += viewport_annotations(
        "th06::AsciiManager::DrawStrings",
        "src/AsciiManager.cpp",
        ["0x00401791", "0x004017a1", "0x004017b1", "0x004017c1"],
        [239, 240, 241, 242],
    )
    rows += viewport_annotations(
        "th06::StageMenu::OnDrawGameMenu",
        "src/AsciiManager.cpp",
        ["0x00402766", "0x00402776", "0x00402786", "0x00402796"],
        [597, 598, 599, 600],
    )
    rows += viewport_annotations(
        "th06::StageMenu::OnDrawRetryMenu",
        "src/AsciiManager.cpp",
        ["0x00403080", "0x00403090", "0x004030a0", "0x004030b0"],
        [808, 809, 810, 811],
    )
    rows += viewport_annotations(
        "th06::AsciiManager::DrawPopupsWithHwVertexProcessing",
        "src/AsciiManager.cpp",
        ["0x004031fa", "0x0040320a", "0x0040321a", "0x0040322a"],
        [847, 848, 849, 850],
    )
    rows += viewport_annotations(
        "th06::AsciiManager::DrawPopupsWithoutHwVertexProcessing",
        "src/AsciiManager.cpp",
        ["0x004033ca", "0x004033da", "0x004033ea", "0x004033fa"],
        [899, 900, 901, 902],
    )
    rows.append(
        annotation(
            "0x00403f4c",
            "th06::Stage::OnUpdate",
            "src/Stage.cpp",
            186,
            "COLOR_SET_COMPONENT(stage->skyFog.color",
            "presentation-color",
            "omit-after-noninterference",
            "eliminate-with-stage-fog-state",
        )
    )
    rows += [
        annotation(
            "0x004060a0",
            "th06::BombData::DarkenViewport",
            "src/BombData.cpp",
            238,
            "(i32)darkeningTimeLeft",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-with-bomb-darkening-draw",
        ),
        annotation(
            "0x00406129",
            "th06::BombData::DarkenViewport",
            "src/BombData.cpp",
            243,
            "(i32)darkeningTimeLeft",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-with-bomb-darkening-draw",
        ),
        annotation(
            "0x0040b38b",
            "th06::EnemyEclInstr::GetVarFloat",
            "src/EnemyEclInstr.cpp",
            240,
            "i32 varId = *eclVarId",
            "ecl-variable-dispatch",
            "retain",
            "prove-truncation-sentinel-classifier--10025-through--10001",
        ),
        annotation(
            "0x0040ebcc",
            "th06::EffectManager::EffectUpdateCallback4",
            "src/EffectManager.cpp",
            143,
            "(i32)(alpha * 255.0f)",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-with-effect-color-or-prove-alpha-0-255",
        ),
        annotation(
            "0x00410a84",
            "th06::Ending::OnDraw",
            "src/Ending.cpp",
            508,
            "ending->backgroundPos.y",
            "ending-draw-rectangle",
            "omit-after-noninterference",
            "eliminate-with-ending-draw",
        ),
        annotation(
            "0x00410a90",
            "th06::Ending::OnDraw",
            "src/Ending.cpp",
            508,
            "ending->backgroundPos.x",
            "ending-draw-rectangle",
            "omit-after-noninterference",
            "eliminate-with-ending-draw",
        ),
        annotation(
            "0x00416003",
            "th06::BulletManager::OnUpdate",
            "src/BulletManager.cpp",
            993,
            "laserColor = curLaser->timer.AsFramesFloat()",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-laser-color-while-retaining-collision-timing",
        ),
        annotation(
            "0x004162eb",
            "th06::BulletManager::OnUpdate",
            "src/BulletManager.cpp",
            1054,
            "laserColor = curLaser->timer.AsFramesFloat()",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-laser-color-while-retaining-collision-timing",
        ),
        annotation(
            "0x00416fbc",
            "th06::BulletManager::AddedCallback",
            "src/BulletManager.cpp",
            1381,
            "bulletHeight =",
            "bullet-render-selection",
            "omit-after-noninterference",
            "prove-bulletHeight-only-selects-draw-path",
        ),
    ]
    rows += viewport_annotations(
        "th06::Gui::DrawStageElements",
        "src/Gui.cpp",
        ["0x0041b137", "0x0041b147", "0x0041b157", "0x0041b167"],
        [1325, 1326, 1328, 1329],
    )
    rows += viewport_annotations(
        "th06::GameManager::OnUpdate",
        "src/GameManager.cpp",
        ["0x0041b7d4", "0x0041b7e7", "0x0041b7fa", "0x0041b80d"],
        [160, 161, 162, 163],
    )
    item_pairs = [
        ("0x0041fb14", "0x0041fb35", 212),
        ("0x0041fb91", "0x0041fbb2", 216),
        ("0x0041fc11", "0x0041fc32", 220),
        ("0x0041fc8e", "0x0041fcaf", 224),
    ]
    for comparison_address, arithmetic_address, call_line in item_pairs:
        rows.append(
            annotation(
                comparison_address,
                "th06::ItemManager::OnUpdate",
                "src/ItemManager.cpp",
                80,
                "(i32)curItem->currentPosition.y < 128",
                "point-item-score",
                "retain",
                "prove-collected-item-y-finite-and-signed-i32",
                inlined_at_line=call_line,
                inlined_at_anchor="calculatePointScore(curItem",
            )
        )
        rows.append(
            annotation(
                arithmetic_address,
                "th06::ItemManager::OnUpdate",
                "src/ItemManager.cpp",
                82,
                "(i32)curItem->currentPosition.y - 128",
                "point-item-score",
                "retain",
                "prove-collected-item-y-finite-and-signed-i32",
                inlined_at_line=call_line,
                inlined_at_anchor="calculatePointScore(curItem",
            )
        )
    rows += [
        annotation(
            "0x00420298",
            "th06::ItemManager::OnDraw",
            "src/ItemManager.cpp",
            382,
            "itemAlpha = 255 - (i32)",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-with-item-draw",
        ),
        annotation(
            "0x00422755",
            "th06::MidiOutput::OnTimerElapsed",
            "src/MidiOutput.cpp",
            459,
            "fadeOutVolumeMultiplier * 128.0f",
            "audio-volume",
            "omit-after-noninterference",
            "eliminate-with-midi-output",
        ),
        annotation(
            "0x0042277e",
            "th06::MidiOutput::OnTimerElapsed",
            "src/MidiOutput.cpp",
            463,
            "fadeOutLastSetVolume =",
            "audio-volume",
            "omit-after-noninterference",
            "eliminate-with-midi-output",
        ),
        annotation(
            "0x00422ec4",
            "th06::MidiOutput::ProcessMsg",
            "src/MidiOutput.cpp",
            632,
            "lVar5 = (f32)arg2",
            "audio-volume",
            "omit-after-noninterference",
            "eliminate-with-midi-output",
        ),
        annotation(
            "0x004232d6",
            "th06::MidiOutput::FadeOutSetVolume",
            "src/MidiOutput.cpp",
            707,
            "volumeClamped = (i32)",
            "audio-volume",
            "omit-after-noninterference",
            "eliminate-with-midi-output",
        ),
        annotation(
            "0x00424da9",
            "th06::Supervisor::FadeOutMusic",
            "src/Supervisor.cpp",
            879,
            "SetFadeOut(1000.0f * fadeOutSeconds)",
            "audio-fade-duration",
            "omit-after-noninterference",
            "eliminate-with-audio-output",
        ),
        annotation(
            "0x00424e74",
            "th06::SoundPlayer::FadeOut",
            "src/SoundPlayer.hpp",
            80,
            "seconds * 60",
            "audio-fade-duration",
            "omit-after-noninterference",
            "eliminate-with-audio-output",
        ),
        annotation(
            "0x00428cc8",
            "th06::Player::OnUpdate",
            "src/Player.cpp",
            234,
            "COLOR_SET_ALPHA(COLOR_WHITE",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-player-sprite-color-while-retaining-respawn-timer",
        ),
        annotation(
            "0x0042f842",
            "th06::ScreenEffect::CalcFadeIn",
            "src/ScreenEffect.cpp",
            43,
            "effect->fadeAlpha = 255.0f",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-fadeAlpha-while-retaining-job-lifetime",
        ),
        annotation(
            "0x0042fcbc",
            "th06::ScreenEffect::CalcFadeOut",
            "src/ScreenEffect.cpp",
            109,
            "effect->fadeAlpha =",
            "presentation-alpha",
            "omit-after-noninterference",
            "eliminate-fadeAlpha-while-retaining-job-lifetime",
        ),
        annotation(
            "0x0043473f",
            "th06::AnmManager::ExecuteScript",
            "src/AnmManager.cpp",
            1312,
            "local_34 =",
            "presentation-color",
            "omit-after-noninterference",
            "eliminate-anm-color-while-retaining-script-timing",
        ),
    ]
    rows += text_argument_annotations(
        "th06::AnmManager::DrawVmTextFmt",
        ["0x00434bc8", "0x00434bda", "0x00434bec", "0x00434bfe"],
        [1399, 1399, 1399, 1398],
        ["textureHeight", "textureWidth", "startPixelInclusive.y", "startPixelInclusive.x"],
    )
    rows += text_argument_annotations(
        "th06::AnmManager::DrawStringFormat",
        ["0x00434cc7", "0x00434cd9", "0x00434ceb", "0x00434cfd"],
        [1418, 1418, 1418, 1417],
        ["textureHeight", "textureWidth", "startPixelInclusive.y", "startPixelInclusive.x"],
    )
    rows.append(
        annotation(
            "0x00434d86",
            "th06::AnmManager::DrawStringFormat",
            "src/AnmManager.cpp",
            1420,
            "secondPartStartX =",
            "text-raster-coordinate",
            "omit-after-noninterference",
            "eliminate-with-text-rasterization",
        )
    )
    rows += text_argument_annotations(
        "th06::AnmManager::DrawStringFormat",
        ["0x00434db6", "0x00434dc8", "0x00434dda"],
        [1423, 1423, 1422],
        ["textureHeight", "textureWidth", "startPixelInclusive.y"],
    )
    rows += text_argument_annotations(
        "th06::AnmManager::DrawStringFormat2",
        ["0x00434ea7", "0x00434eb9", "0x00434ecb", "0x00434edd"],
        [1442, 1442, 1442, 1441],
        ["textureHeight", "textureWidth", "startPixelInclusive.y", "startPixelInclusive.x"],
    )
    rows.append(
        annotation(
            "0x00434f6c",
            "th06::AnmManager::DrawStringFormat2",
            "src/AnmManager.cpp",
            1444,
            "secondPartStartX =",
            "text-raster-coordinate",
            "omit-after-noninterference",
            "eliminate-with-text-rasterization",
        )
    )
    rows += text_argument_annotations(
        "th06::AnmManager::DrawStringFormat2",
        ["0x00434f9c", "0x00434fae", "0x00434fc0"],
        [1447, 1447, 1446],
        ["textureHeight", "textureWidth", "startPixelInclusive.y"],
    )
    return rows


def pinned_blob(source_root: Path, source_file: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(source_root), "show", f"{UPSTREAM_REVISION}:{source_file}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"cannot read {source_file} at {UPSTREAM_REVISION}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def verify_source_candidate(source_text: str, source: dict[str, Any]) -> None:
    lines = source_text.splitlines()
    line = source["line"]
    if line <= 0 or line > len(lines) or source["line_anchor"] not in lines[line - 1]:
        raise ValueError(
            f"source anchor mismatch at {source['file']}:{line}: "
            f"{source['line_anchor']!r}"
        )
    if "inlined_at_line" in source:
        inline_line = source["inlined_at_line"]
        inline_anchor = source["inlined_at_anchor"]
        if (
            inline_line <= 0
            or inline_line > len(lines)
            or inline_anchor not in lines[inline_line - 1]
        ):
            raise ValueError(
                f"inline anchor mismatch at {source['file']}:{inline_line}: "
                f"{inline_anchor!r}"
            )


def build_document(ledger: dict[str, Any], source_root: Path, tool_path: Path) -> dict[str, Any]:
    if arithmetic_obligations.document_digest(ledger) != ledger.get("artifact_sha256"):
        raise ValueError("base arithmetic obligation ledger has an invalid digest")
    base_sites = {
        site["call_address"]: site for site in ledger["sites"]["ftol2_calls"]
    }
    rows = annotations()
    annotated = {row["call_address"]: row for row in rows}
    if len(annotated) != len(rows):
        raise ValueError("duplicate source-candidate call address")
    if set(annotated) != set(base_sites):
        missing = sorted(set(base_sites) - set(annotated))
        extra = sorted(set(annotated) - set(base_sites))
        raise ValueError(f"source-candidate coverage mismatch: missing={missing}, extra={extra}")

    source_blobs: dict[str, bytes] = {}
    for row in rows:
        base = base_sites[row["call_address"]]
        if base["function"] != row["function"]:
            raise ValueError(
                f"function mismatch at {row['call_address']}: "
                f"{row['function']} != {base['function']}"
            )
        source_file = row["source_candidate"]["file"]
        if source_file not in source_blobs:
            source_blobs[source_file] = pinned_blob(source_root, source_file)
        blob = source_blobs[source_file]
        verify_source_candidate(blob.decode("utf-8"), row["source_candidate"])
        row["base_obligation_id"] = base["id"]

    rows.sort(key=lambda row: row["call_address"])
    disposition_counts = Counter(row["candidate_disposition"] for row in rows)
    sink_counts = Counter(row["semantic_sink"] for row in rows)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "base_ledger_artifact_sha256": ledger["artifact_sha256"],
        "generator": {
            "path": "tools/ftol2_source_candidates.py",
            "sha256": arithmetic_obligations.sha256_file(tool_path),
        },
        "upstream": {
            "url": UPSTREAM_URL,
            "revision": UPSTREAM_REVISION,
            "source_files": {
                source_file: hashlib.sha256(blob).hexdigest()
                for source_file, blob in sorted(source_blobs.items())
            },
        },
        "method": {
            "status": CORRESPONDENCE_STATUS,
            "claim": (
                "Candidates align mapped function ownership, call-site disassembly data flow, "
                "source order, and pinned source anchors. They are not debug-line evidence, "
                "a compiler-correctness theorem, or a slicing proof."
            ),
            "disposition_rule": (
                "retain means the operation currently affects the gameplay projection; "
                "omit-after-noninterference remains retained until a transitive projection "
                "noninterference theorem is attached."
            ),
        },
        "counts": {
            "sites": len(rows),
            "candidate_dispositions": dict(sorted(disposition_counts.items())),
            "semantic_sinks": dict(sorted(sink_counts.items())),
        },
        "sites": rows,
    }
    return arithmetic_obligations.seal(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", type=Path, default=Path("arithmetic/obligations-v1.json")
    )
    parser.add_argument("--source-root", type=Path, required=True)
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--check", type=Path)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text())
    document = build_document(ledger, args.source_root, Path(__file__).resolve())
    output = arithmetic_obligations.render(document)
    if args.check is not None:
        if args.check.read_text() != output:
            print(f"stale __ftol2 source-candidate ledger: {args.check}", file=sys.stderr)
            return 1
        print(f"verified current __ftol2 source-candidate ledger: {args.check}")
        return 0
    if args.output is not None:
        args.output.write_text(output)
        print(f"wrote {args.output} ({document['artifact_sha256']})")
        return 0
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

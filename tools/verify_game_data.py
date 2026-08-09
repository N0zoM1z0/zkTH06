#!/usr/bin/env python3
"""Verify a local TH06 v1.02h runtime directory against the pinned manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(directory: Path, manifest_path: Path) -> tuple[dict[str, Any], bool]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    valid = True
    for entry in manifest["required_files"]:
        path = directory / entry["filename"]
        actual = sha256_file(path) if path.is_file() else None
        matches = actual == entry["sha256"]
        valid = valid and matches
        results.append(
            {
                "filename": entry["filename"],
                "role": entry["role"],
                "expected_sha256": entry["sha256"],
                "actual_sha256": actual,
                "valid": matches,
            }
        )
    return {"directory": str(directory), "valid": valid, "files": results}, valid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    try:
        report, valid = verify(args.directory, args.manifest)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"data verification failed: {exc}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

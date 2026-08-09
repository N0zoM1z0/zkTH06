#!/usr/bin/env python3
"""Build and run the pinned x87/SoftFloat result-bit differential probe."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile


UPSTREAM_URL = "https://github.com/ucb-bar/berkeley-softfloat-3.git"
PINNED_REVISION = "f74b1e48110ac3a27dd49b787d164e55e42d81d1"

# These hashes are redundant with the pinned Git object, but make accidental
# changes to the selected platform/header contract fail visibly.
PINNED_FILE_HASHES = {
    "COPYING.txt": "145ea96b4a4a04a1a7738d2a2bf9e830f861971e69606187b018d9e8fc0b95c7",
    "build/Linux-x86_64-GCC/platform.h": (
        "2ae1992fc5f0d35e65ee3fd5ca2a4471385b78b0317403f66b304cb799a777d1"
    ),
    "source/include/softfloat.h": (
        "27c5f39c21e10e1e798457cdfada111cc2e440a17acba8804e6a2b0a1d7833fc"
    ),
    "source/softfloat_state.c": (
        "5f7a70c4c5823cdde0518db77a74a6549dba62b21d910f6dadb9115b1d478301"
    ),
}

SOFTFLOAT_SOURCES = (
    "source/extF80_add.c",
    "source/extF80_div.c",
    "source/extF80_mul.c",
    "source/extF80_sqrt.c",
    "source/extF80_sub.c",
    "source/f32_to_extF80.c",
    "source/s_addMagsExtF80.c",
    "source/s_approxRecipSqrt32_1.c",
    "source/s_approxRecipSqrt_1Ks.c",
    "source/8086/s_commonNaNToExtF80UI.c",
    "source/8086/s_f32UIToCommonNaN.c",
    "source/s_normRoundPackToExtF80.c",
    "source/s_normSubnormalExtF80Sig.c",
    "source/s_normSubnormalF32Sig.c",
    "source/8086/s_propagateNaNExtF80UI.c",
    "source/s_roundPackToExtF80.c",
    "source/s_shiftRightJam128.c",
    "source/s_subMagsExtF80.c",
    "source/8086/softfloat_raiseFlags.c",
    "source/softfloat_state.c",
)


class ProbeError(RuntimeError):
    """An expected reproducibility or build failure."""


def positive_count(text: str) -> int:
    try:
        value = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value


def run_git(repo: Path, *arguments: str, capture: bool = True) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", os.fspath(repo), *arguments],
            check=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ProbeError("git is required to export the pinned source") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise ProbeError(detail or f"git {' '.join(arguments)} failed") from exc
    return completed.stdout if capture else b""


def export_pinned_tree(repo: Path, destination: Path) -> None:
    if not repo.is_dir():
        raise ProbeError(
            f"SoftFloat checkout not found at {repo}\n"
            f"clone it with: git clone {UPSTREAM_URL} {repo}\n"
            f"then pin it with: git -C {repo} checkout {PINNED_REVISION}"
        )

    resolved = run_git(repo, "rev-parse", f"{PINNED_REVISION}^{{commit}}")
    if resolved.decode("ascii").strip() != PINNED_REVISION:
        raise ProbeError(f"checkout does not contain pinned commit {PINNED_REVISION}")

    archive = run_git(repo, "archive", "--format=tar", PINNED_REVISION)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ProbeError(f"unsafe path in pinned archive: {member.name}")
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                source = bundle.extractfile(member)
                if source is None:
                    raise ProbeError(f"could not read archive member: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
            else:
                raise ProbeError(f"unsupported archive member: {member.name}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_export(source: Path) -> None:
    for relative, expected in PINNED_FILE_HASHES.items():
        path = source / relative
        actual = sha256(path)
        if actual != expected:
            raise ProbeError(
                f"pinned-file hash mismatch for {relative}: expected {expected}, got {actual}"
            )
    for relative in SOFTFLOAT_SOURCES:
        if not (source / relative).is_file():
            raise ProbeError(f"pinned source is missing {relative}")


def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def compiler_identity(compiler: str) -> str:
    completed = subprocess.run(
        [compiler, "--version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout.splitlines()[0] if completed.stdout else compiler


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "compare x87 CW 0x027f basic-operation result bits with pinned "
            "Berkeley SoftFloat Release 3e"
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "repos" / "berkeley-softfloat-3",
        help="Git checkout containing the pinned SoftFloat commit",
    )
    parser.add_argument("--cc", default="cc", help="C compiler command")
    parser.add_argument(
        "--cases",
        type=positive_count,
        default=1_000_000,
        help="deterministic random cases per operation and input class",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    machine = platform.machine().lower()
    if machine not in {"amd64", "x86_64"}:
        raise ProbeError(
            "the pinned 20-file SoftFloat build profile requires x86-64; "
            f"detected {machine}"
        )

    compiler = shutil.which(args.cc)
    if compiler is None:
        raise ProbeError(f"C compiler not found: {args.cc}")

    root = Path(__file__).resolve().parents[1]
    probe = root / "arithmetic" / "softfloat_probe.c"
    if not probe.is_file():
        raise ProbeError(f"probe source not found: {probe}")

    with tempfile.TemporaryDirectory(prefix="zkth06-softfloat-") as temporary:
        temporary_root = Path(temporary)
        source = temporary_root / "softfloat"
        source.mkdir()
        export_pinned_tree(args.source.resolve(), source)
        verify_export(source)

        executable = temporary_root / "softfloat_probe"
        command = [
            compiler,
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DSOFTFLOAT_FAST_INT64",
            "-DSOFTFLOAT_ROUND_ODD",
            "-DINLINE_LEVEL=5",
            "-DSOFTFLOAT_FAST_DIV32TO16",
            "-DSOFTFLOAT_FAST_DIV64TO32",
            f"-I{source / 'build/Linux-x86_64-GCC'}",
            f"-I{source / 'source/8086'}",
            f"-I{source / 'source/include'}",
            os.fspath(probe),
            *(os.fspath(source / relative) for relative in SOFTFLOAT_SOURCES),
            "-o",
            os.fspath(executable),
        ]
        subprocess.run(command, check=True)

        print(f"SoftFloat revision: {PINNED_REVISION}")
        print(f"probe SHA-256: {sha256(probe)}")
        print(f"host architecture: {machine}")
        print(f"host CPU: {cpu_model()}")
        print(f"compiler: {compiler_identity(compiler)}", flush=True)
        completed = subprocess.run(
            [os.fspath(executable), str(args.cases), str(args.cases)],
            check=False,
        )
        return completed.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ProbeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)

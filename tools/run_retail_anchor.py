#!/usr/bin/env python3
"""Run a pinned TH06 retail replay under Wine and export frame anchors."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.json"
GDB_SCRIPT = ROOT / "tools" / "gdb" / "retail_anchor_trace.py"
CONFIG_NAME = "東方紅魔郷.cfg"
REPLAY_SLOT = "th6_udZKVM.rpy"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_version(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return (completed.stdout or completed.stderr).splitlines()[0].strip()


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"required command is unavailable: {name}")
    return path


def validate_retail_dir(retail_dir: Path) -> tuple[dict[str, Any], Path]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["required_files"]:
        path = retail_dir / entry["filename"]
        if not path.is_file():
            raise RuntimeError(f"missing pinned retail file: {path}")
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise RuntimeError(
                f"retail file hash mismatch for {entry['filename']}: "
                f"expected={entry['sha256']} actual={actual}"
            )
    config = retail_dir / CONFIG_NAME
    if not config.is_file():
        raise RuntimeError(
            f"missing windowed retail configuration: {config}; run th06_config under Wine first"
        )
    return manifest, config


def choose_display() -> int:
    for number in range(120, 200):
        if not Path(f"/tmp/.X11-unix/X{number}").exists() and not Path(
            f"/tmp/.X{number}-lock"
        ).exists():
            return number
    raise RuntimeError("no free X display in :120..:199")


def stop_process_group(process: subprocess.Popen[object] | None) -> None:
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)


def wait_for_x(display: int, process: subprocess.Popen[object]) -> None:
    socket = Path(f"/tmp/.X11-unix/X{display}")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Xvfb exited before creating its display socket")
        if socket.exists():
            return
        time.sleep(0.05)
    raise RuntimeError(f"Xvfb did not make :{display} ready")


def prepare_run_dir(
    run_dir: Path,
    retail_dir: Path,
    manifest: dict[str, Any],
    config: Path,
    replay: Path,
) -> None:
    for entry in manifest["required_files"]:
        source = (retail_dir / entry["filename"]).resolve()
        (run_dir / entry["filename"]).symlink_to(source)
    shutil.copy2(config, run_dir / CONFIG_NAME)
    replay_dir = run_dir / "replay"
    replay_dir.mkdir()
    shutil.copy2(replay, replay_dir / REPLAY_SLOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retail-dir", required=True, type=Path)
    parser.add_argument("--replay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument(
        "--timeout",
        type=int,
        help="GDB capture timeout in seconds (default scales with frame count)",
    )
    parser.add_argument("--force", action="store_true", help="replace output and logs")
    args = parser.parse_args()

    if args.frames <= 0:
        parser.error("--frames must be positive")
    retail_dir = args.retail_dir.expanduser().resolve()
    replay = args.replay.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not replay.is_file():
        parser.error(f"replay does not exist: {replay}")

    wine = require_tool("wine")
    xvfb = require_tool("Xvfb")
    gdb = require_tool("gdb")
    sudo = require_tool("sudo")
    subprocess.run([sudo, "-n", "true"], check=True)
    all_locales = subprocess.run(
        ["locale", "-a"], check=True, text=True, capture_output=True
    ).stdout.lower()
    if "ja_jp.utf8" not in all_locales and "ja_jp.utf-8" not in all_locales:
        raise RuntimeError("ja_JP.UTF-8 locale is required for retail TH06 filenames")

    manifest, config = validate_retail_dir(retail_dir)
    replay_hash = sha256_file(replay)
    config_hash = sha256_file(config)
    wine_version = command_version([wine, "--version"])
    gdb_version = command_version([gdb, "--version"])

    output.parent.mkdir(parents=True, exist_ok=True)
    gdb_log = output.with_suffix(output.suffix + ".gdb.log")
    wine_log = output.with_suffix(output.suffix + ".wine.log")
    claimed_paths = (output, gdb_log, wine_log)
    existing = [path for path in claimed_paths if path.exists()]
    if existing and not args.force:
        parser.error("output exists (pass --force): " + ", ".join(map(str, existing)))
    for path in claimed_paths:
        path.write_bytes(b"")

    display = choose_display()
    xvfb_process: subprocess.Popen[object] | None = None
    wine_process: subprocess.Popen[object] | None = None
    gdb_process: subprocess.Popen[object] | None = None
    timeout = args.timeout if args.timeout is not None else max(120, args.frames // 20)

    with tempfile.TemporaryDirectory(prefix="zkth06-retail-anchor-") as temporary:
        run_dir = Path(temporary)
        prepare_run_dir(run_dir, retail_dir, manifest, config, replay)
        try:
            xvfb_process = subprocess.Popen(
                [
                    xvfb,
                    f":{display}",
                    "-screen",
                    "0",
                    "1024x768x24",
                    "-ac",
                    "+extension",
                    "GLX",
                    "+render",
                    "-noreset",
                    "-nolisten",
                    "tcp",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            wait_for_x(display, xvfb_process)

            environment = os.environ.copy()
            environment.update(
                {
                    "DISPLAY": f":{display}",
                    "LANG": "ja_JP.UTF-8",
                    "LC_ALL": "ja_JP.UTF-8",
                    "WINEDEBUG": "-all",
                    "LP_NUM_THREADS": "1",
                    "MESA_GLTHREAD": "false",
                }
            )
            with wine_log.open("wb") as wine_output:
                wine_process = subprocess.Popen(
                    [wine, f"./{manifest['required_files'][0]['filename']}"],
                    cwd=run_dir,
                    env=environment,
                    stdout=wine_output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                time.sleep(1)
                if wine_process.poll() is not None:
                    raise RuntimeError(f"retail TH06 exited early; inspect {wine_log}")

                gdb_command = [
                    sudo,
                    "-n",
                    "env",
                    f"ZKTH06_RETAIL_TRACE_OUTPUT={output}",
                    f"ZKTH06_RETAIL_TRACE_FRAMES={args.frames}",
                    f"ZKTH06_WINE_VERSION={wine_version}",
                    f"ZKTH06_GDB_VERSION={gdb_version}",
                    f"ZKTH06_RETAIL_REPLAY_SHA256={replay_hash}",
                    f"ZKTH06_RETAIL_CONFIG_SHA256={config_hash}",
                    gdb,
                    "-nx",
                    "-q",
                    "-batch",
                    "-ex",
                    "set pagination off",
                    "-ex",
                    "set print thread-events off",
                    "-ex",
                    f"attach {wine_process.pid}",
                    "-x",
                    str(GDB_SCRIPT),
                ]
                with gdb_log.open("wb") as debugger_output:
                    gdb_process = subprocess.Popen(
                        gdb_command,
                        stdout=debugger_output,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    try:
                        gdb_status = gdb_process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired as exc:
                        stop_process_group(gdb_process)
                        raise RuntimeError(
                            f"retail anchor capture exceeded {timeout}s; inspect {gdb_log}"
                        ) from exc
                if gdb_status != 0:
                    raise RuntimeError(
                        f"retail anchor GDB exited with status {gdb_status}; inspect {gdb_log}"
                    )
        finally:
            stop_process_group(gdb_process)
            stop_process_group(wine_process)
            stop_process_group(xvfb_process)

    row_count = sum(1 for _ in output.open(encoding="utf-8"))
    if row_count != args.frames + 1:
        raise RuntimeError(
            f"retail trace row count mismatch: expected={args.frames + 1} actual={row_count}"
        )
    print(
        json.dumps(
            {
                "status": "captured",
                "frames": args.frames,
                "retail_trace": str(output),
                "gdb_log": str(gdb_log),
                "wine_log": str(wine_log),
                "replay_sha256": replay_hash,
                "target_executable_sha256": manifest["required_files"][0]["sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

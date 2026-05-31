"""Development-only graceful reload runner for the Pre worker.

This module mimics FastAPI's reload ergonomics without killing an active Pre
job mid-calculation. On source changes it asks the child Pre process to stop;
the child finishes the current job, exits, and only then this runner starts a
fresh process with the changed code.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


LOGGER = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WATCH_PATHS = (BACKEND_ROOT / "app",)


@dataclass(slots=True)
class WatchSnapshot:
    files: dict[Path, int]


def _resolve_watch_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path.resolve()


def _iter_python_files(paths: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*.py"):
            if "__pycache__" in candidate.parts:
                continue
            files.append(candidate)
    return sorted(set(files))


def _snapshot(paths: tuple[Path, ...]) -> WatchSnapshot:
    file_mtimes: dict[Path, int] = {}
    for path in _iter_python_files(paths):
        try:
            file_mtimes[path] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return WatchSnapshot(files=file_mtimes)


def _changed_files(previous: WatchSnapshot, current: WatchSnapshot) -> list[Path]:
    changed: list[Path] = []
    previous_files = previous.files
    current_files = current.files
    for path, mtime_ns in current_files.items():
        if previous_files.get(path) != mtime_ns:
            changed.append(path)
    for path in previous_files:
        if path not in current_files:
            changed.append(path)
    return sorted(changed)


def _start_pre_worker(*, worker_name: str) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["FORGELAB_WORKER_NAME"] = worker_name
    command = [sys.executable, "-m", "app.workers.pre_worker"]
    LOGGER.info("Starting Pre worker worker_name=%s command=%s", worker_name, " ".join(command))
    return subprocess.Popen(command, cwd=BACKEND_ROOT, env=env)


def _request_graceful_stop(process: subprocess.Popen[bytes], *, reason: str) -> None:
    if process.poll() is not None:
        return
    LOGGER.info("Requesting graceful Pre worker stop pid=%s reason=%s", process.pid, reason)
    if os.name == "nt":
        # Windows has no POSIX SIGTERM delivery semantics for child Python
        # console processes. This runner is intended for Linux development;
        # terminate is still better than leaving a duplicate dev worker.
        process.terminate()
        return
    process.send_signal(signal.SIGTERM)


def _wait_for_child_exit(process: subprocess.Popen[bytes]) -> None:
    while process.poll() is None:
        time.sleep(0.2)


def _format_changed_files(paths: list[Path], *, limit: int = 5) -> str:
    if not paths:
        return ""
    labels = [str(path.relative_to(BACKEND_ROOT)) if path.is_relative_to(BACKEND_ROOT) else str(path) for path in paths[:limit]]
    suffix = "" if len(paths) <= limit else f", +{len(paths) - limit} more"
    return ", ".join(labels) + suffix


def run_dev_reload(
    *,
    worker_name: str,
    watch_paths: tuple[Path, ...],
    poll_interval_seconds: float,
    shutdown_warning_seconds: float,
) -> int:
    LOGGER.info(
        "Pre graceful reload runner started worker_name=%s watch_paths=%s",
        worker_name,
        [str(path) for path in watch_paths],
    )
    snapshot = _snapshot(watch_paths)
    child = _start_pre_worker(worker_name=worker_name)
    stop_requested = False
    reload_requested = False
    reload_requested_at: float | None = None
    last_wait_warning_at = 0.0

    def request_runner_stop(signum: int, _frame: object | None) -> None:
        nonlocal stop_requested
        LOGGER.info("Pre graceful reload runner received signal=%s", signum)
        stop_requested = True
        _request_graceful_stop(child, reason="runner_shutdown")

    signal.signal(signal.SIGINT, request_runner_stop)
    signal.signal(signal.SIGTERM, request_runner_stop)

    try:
        while not stop_requested:
            time.sleep(max(poll_interval_seconds, 0.1))

            current_snapshot = _snapshot(watch_paths)
            changed = _changed_files(snapshot, current_snapshot)
            snapshot = current_snapshot

            if changed and not reload_requested:
                reload_requested = True
                reload_requested_at = time.monotonic()
                last_wait_warning_at = reload_requested_at
                LOGGER.info(
                    "Pre source change detected; reload will start after current job exits changed=%s",
                    _format_changed_files(changed),
                )
                _request_graceful_stop(child, reason="source_change")
            elif changed:
                LOGGER.info(
                    "Additional Pre source changes detected while waiting for graceful exit changed=%s",
                    _format_changed_files(changed),
                )

            return_code = child.poll()
            if return_code is None:
                if reload_requested and reload_requested_at is not None:
                    now = time.monotonic()
                    if now - last_wait_warning_at >= shutdown_warning_seconds:
                        LOGGER.warning(
                            "Waiting for Pre worker pid=%s to finish current job before reload; waited %.0fs",
                            child.pid,
                            now - reload_requested_at,
                        )
                        last_wait_warning_at = now
                continue

            if reload_requested:
                LOGGER.info("Pre worker exited for graceful reload pid=%s return_code=%s", child.pid, return_code)
            else:
                LOGGER.warning("Pre worker exited unexpectedly pid=%s return_code=%s; restarting", child.pid, return_code)
            reload_requested = False
            reload_requested_at = None
            child = _start_pre_worker(worker_name=worker_name)
    finally:
        _request_graceful_stop(child, reason="runner_exit")
        _wait_for_child_exit(child)
        LOGGER.info("Pre graceful reload runner stopped")

    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Pre worker with development-only graceful reload.")
    parser.add_argument(
        "--worker-name",
        default=os.getenv("FORGELAB_WORKER_NAME", "pre-1"),
        help="Pre worker instance name. Defaults to FORGELAB_WORKER_NAME or pre-1.",
    )
    parser.add_argument(
        "--watch-path",
        action="append",
        default=None,
        help="Python file or directory to watch. May be repeated. Defaults to backend/app.",
    )
    parser.add_argument("--poll-interval", type=float, default=1.0, help="File polling interval in seconds.")
    parser.add_argument(
        "--shutdown-warning-seconds",
        type=float,
        default=30.0,
        help="Warn repeatedly while waiting for active Pre job to finish before reload.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(sys.argv[1:] if argv is None else argv)
    raw_watch_paths = args.watch_path or [str(path) for path in DEFAULT_WATCH_PATHS]
    watch_paths = tuple(_resolve_watch_path(path) for path in raw_watch_paths)
    return run_dev_reload(
        worker_name=args.worker_name,
        watch_paths=watch_paths,
        poll_interval_seconds=args.poll_interval,
        shutdown_warning_seconds=args.shutdown_warning_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())

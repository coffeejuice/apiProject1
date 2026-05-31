#!/usr/bin/env python3
"""Development launcher for the local ForgeLab home-lab workstation.

This is intentionally a small local-development helper, not a production
process manager. It starts the usual development processes, prefixes their
logs, and stops them together on Ctrl+C.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DEFAULT_API_PORT = 8001
DEFAULT_FRONTEND_PORT = 5173
PROFILE_TO_PROCESSES = {
    "all": ("frontend", "api", "pre", "post", "solver"),
    "core": ("frontend", "api", "pre"),
    "api-pre": ("api", "pre"),
    "workers": ("pre", "post", "solver"),
    "frontend": ("frontend",),
    "api": ("api",),
    "pre": ("pre",),
    "post": ("post",),
    "solver": ("solver",),
}
LOG_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
    "FATAL": 50,
}
TERMINAL_LOG_LEVEL = "ERROR"
LOG_LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b", re.IGNORECASE)
_HOSTNAME = socket.gethostname()
_LOGS_ROOT_CACHE: Path | None = None


@dataclass(slots=True)
class DevProcessSpec:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)
    port: int | None = None
    log_service: str | None = None
    log_worker: str | None = None


@dataclass(slots=True)
class RunningProcess:
    spec: DevProcessSpec
    process: subprocess.Popen[str]
    reader_thread: threading.Thread


def backend_python() -> Path:
    candidates = [
        BACKEND_DIR / ".venv" / "bin" / "python",
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Backend virtual environment was not found. Expected backend/.venv/bin/python "
        "or backend/.venv/Scripts/python.exe."
    )


def configured_logs_root() -> Path:
    global _LOGS_ROOT_CACHE
    if _LOGS_ROOT_CACHE is not None:
        return _LOGS_ROOT_CACHE

    env_path = BACKEND_DIR / ".env"
    configured_root: Path | None = None
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "LOGS_FILES_ROOT":
                configured_root = Path(value.strip().strip('"').strip("'")).expanduser()
                break

    for candidate in (configured_root, BACKEND_DIR / "logs"):
        if candidate is None:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe_path = candidate / ".forgelab-dev-write-test"
            probe_path.write_text("", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            _LOGS_ROOT_CACHE = candidate
            return candidate
        except OSError:
            continue

    fallback_root = BACKEND_DIR / "logs"
    fallback_root.mkdir(parents=True, exist_ok=True)
    _LOGS_ROOT_CACHE = fallback_root
    return fallback_root


def dev_log_file_path(*, service: str, worker_name: str) -> Path:
    normalized_service = service.strip().lower()
    normalized_worker = worker_name.strip() or normalized_service
    return configured_logs_root() / normalized_service / f"{normalized_worker}.jsonl"


def port_is_open(port: int, *, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def resolve_profiles(raw_profiles: list[str]) -> list[str]:
    profiles = raw_profiles or ["all"]
    unknown = [profile for profile in profiles if profile not in PROFILE_TO_PROCESSES]
    if unknown:
        raise RuntimeError(
            f"Unknown profile(s): {', '.join(unknown)}. "
            f"Available profiles: {', '.join(PROFILE_TO_PROCESSES)}."
        )

    names: list[str] = []
    for profile in profiles:
        for name in PROFILE_TO_PROCESSES[profile]:
            if name not in names:
                names.append(name)
    return names


def process_specs(
    names: list[str],
    *,
    pre_worker_name: str,
    post_worker_name: str,
    solver_worker_name: str,
    pre_reload: bool,
) -> list[DevProcessSpec]:
    specs: list[DevProcessSpec] = []
    for name in names:
        if name == "frontend":
            specs.append(
                DevProcessSpec(
                    name="front",
                    command=["npm", "run", "dev"],
                    cwd=FRONTEND_DIR,
                    port=DEFAULT_FRONTEND_PORT,
                    log_service="frontend",
                    log_worker="frontend",
                )
            )
            continue

        python = str(backend_python())
        if name == "api":
            specs.append(
                DevProcessSpec(
                    name="api",
                    command=[python, "run.py"],
                    cwd=BACKEND_DIR,
                    port=DEFAULT_API_PORT,
                    log_service="api",
                    log_worker="api-console",
                )
            )
            continue

        if name == "pre":
            specs.append(
                DevProcessSpec(
                    name="pre",
                    command=[python, "-m", "app.workers.pre_dev_reload" if pre_reload else "app.workers.pre_worker"],
                    cwd=BACKEND_DIR,
                    env={"FORGELAB_WORKER_NAME": pre_worker_name},
                    log_service="pre",
                    log_worker=f"{pre_worker_name}-console",
                )
            )
            continue

        if name == "post":
            specs.append(
                DevProcessSpec(
                    name="post",
                    command=[python, "-m", "app.workers.post_worker"],
                    cwd=BACKEND_DIR,
                    env={"FORGELAB_WORKER_NAME": post_worker_name},
                    log_service="post",
                    log_worker=f"{post_worker_name}-console",
                )
            )
            continue

        if name == "solver":
            specs.append(
                DevProcessSpec(
                    name="solver",
                    command=[python, "-m", "app.workers.solver_worker"],
                    cwd=BACKEND_DIR,
                    env={"FORGELAB_WORKER_NAME": solver_worker_name},
                    log_service="solver",
                    log_worker=f"{solver_worker_name}-console",
                )
            )
            continue

        raise RuntimeError(f"Unsupported process name: {name}")

    return specs


def check_prerequisites(specs: list[DevProcessSpec], *, allow_used_ports: bool) -> None:
    if not BACKEND_DIR.exists():
        raise RuntimeError(f"Backend directory does not exist: {BACKEND_DIR}")
    if not FRONTEND_DIR.exists():
        raise RuntimeError(f"Frontend directory does not exist: {FRONTEND_DIR}")

    selected_names = {spec.name for spec in specs}
    if "front" in selected_names:
        if shutil.which("npm") is None:
            raise RuntimeError("npm was not found in PATH.")
        if not (FRONTEND_DIR / "node_modules").exists():
            raise RuntimeError("frontend/node_modules was not found. Run npm install in frontend/ first.")
    if "api" in selected_names or "pre" in selected_names:
        python = backend_python()
        if not python.exists():
            raise RuntimeError(f"Backend Python executable was not found: {python}")
        if not (BACKEND_DIR / ".env").exists():
            raise RuntimeError("backend/.env was not found.")

    blocked_ports = [spec.port for spec in specs if spec.port is not None and port_is_open(spec.port)]
    if blocked_ports and not allow_used_ports:
        ports = ", ".join(str(port) for port in blocked_ports)
        raise RuntimeError(
            f"Required dev port(s) already listen: {ports}. "
            "Stop existing dev processes or rerun with --allow-used-ports."
        )


def popen_start_new_group_kwargs() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def line_log_level(line: str) -> str:
    match = LOG_LEVEL_PATTERN.search(line)
    if match:
        level = match.group(1).upper()
        return "WARNING" if level == "WARN" else "CRITICAL" if level == "FATAL" else level
    lowered = line.lower()
    if "traceback" in lowered or "exception" in lowered or "error" in lowered or "failed" in lowered:
        return "ERROR"
    return "INFO"


def should_print_to_terminal(level: str) -> bool:
    return LOG_LEVEL_ORDER.get(level, LOG_LEVEL_ORDER["INFO"]) >= LOG_LEVEL_ORDER[TERMINAL_LOG_LEVEL]


def append_launcher_log(spec: DevProcessSpec, *, process_id: int, line: str, level: str) -> None:
    if not spec.log_service or not spec.log_worker:
        return
    path = dev_log_file_path(service=spec.log_service, worker_name=spec.log_worker)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "service": spec.log_service,
        "worker_name": spec.log_worker,
        "hostname": _HOSTNAME,
        "pid": process_id,
        "logger": f"dev.launcher.{spec.name}",
        "module": "dev",
        "function": "read_prefixed_output",
        "line": 0,
        "message": line.rstrip("\n"),
        "source_stream": "stdout",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def read_prefixed_output(spec: DevProcessSpec, process_id: int, stream: object) -> None:
    assert hasattr(stream, "readline")
    while True:
        line = stream.readline()
        if not line:
            return
        level = line_log_level(line)
        append_launcher_log(spec, process_id=process_id, line=line, level=level)
        if should_print_to_terminal(level):
            print(f"[{spec.name}] {line}", end="", flush=True)


def start_process(spec: DevProcessSpec) -> RunningProcess:
    env = os.environ.copy()
    env.update(spec.env)
    process = subprocess.Popen(
        spec.command,
        cwd=spec.cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **popen_start_new_group_kwargs(),
    )
    assert process.stdout is not None
    reader = threading.Thread(
        target=read_prefixed_output,
        args=(spec, process.pid, process.stdout),
        name=f"{spec.name}-log-reader",
        daemon=True,
    )
    reader.start()
    log_path = (
        dev_log_file_path(service=spec.log_service, worker_name=spec.log_worker)
        if spec.log_service and spec.log_worker
        else None
    )
    log_note = f" log_file={log_path}" if log_path is not None else ""
    print(f"[dev] started {spec.name} pid={process.pid}{log_note} command={' '.join(spec.command)}", flush=True)
    return RunningProcess(spec=spec, process=process, reader_thread=reader)


def request_stop(running: RunningProcess) -> None:
    process = running.process
    if process.poll() is not None:
        return
    print(f"[dev] stopping {running.spec.name} pid={process.pid}", flush=True)
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def force_stop(running: RunningProcess) -> None:
    process = running.process
    if process.poll() is not None:
        return
    print(f"[dev] force stopping {running.spec.name} pid={process.pid}", flush=True)
    try:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def stop_all(running_processes: list[RunningProcess], *, timeout_seconds: float) -> None:
    for running in running_processes:
        request_stop(running)

    deadline = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None
    while True:
        alive = [running for running in running_processes if running.process.poll() is None]
        if not alive:
            return
        if deadline is not None and time.monotonic() >= deadline:
            for running in alive:
                force_stop(running)
            return
        time.sleep(0.2)


def run_processes(specs: list[DevProcessSpec], *, shutdown_timeout_seconds: float) -> int:
    running_processes = [start_process(spec) for spec in specs]
    print("[dev] all selected processes started. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            for running in running_processes:
                return_code = running.process.poll()
                if return_code is not None:
                    print(
                        f"[dev] {running.spec.name} exited with code {return_code}; stopping remaining processes.",
                        flush=True,
                    )
                    stop_all(running_processes, timeout_seconds=shutdown_timeout_seconds)
                    return return_code if return_code != 0 else 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dev] Ctrl+C received; stopping selected processes.", flush=True)
        stop_all(running_processes, timeout_seconds=shutdown_timeout_seconds)
        return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start local ForgeLab development processes.")
    parser.add_argument(
        "profiles",
        nargs="*",
        help="Profiles to start: all, core, frontend, api, pre, post, solver, workers, api-pre. Defaults to all.",
    )
    parser.add_argument(
        "--pre-worker-name",
        default=os.getenv("FORGELAB_WORKER_NAME", "pre-1"),
        help="Pre worker instance name. Defaults to FORGELAB_WORKER_NAME or pre-1.",
    )
    parser.add_argument(
        "--post-worker-name",
        default=os.getenv("FORGELAB_POST_WORKER_NAME", "post-1"),
        help="Post worker instance name. Defaults to FORGELAB_POST_WORKER_NAME or post-1.",
    )
    parser.add_argument(
        "--solver-worker-name",
        default=os.getenv("FORGELAB_SOLVER_WORKER_NAME", "solver-1"),
        help="Solver worker instance name. Defaults to FORGELAB_SOLVER_WORKER_NAME or solver-1.",
    )
    parser.add_argument(
        "--no-pre-reload",
        action="store_true",
        help="Run plain app.workers.pre_worker instead of graceful pre_dev_reload.",
    )
    parser.add_argument(
        "--allow-used-ports",
        action="store_true",
        help="Do not fail when frontend/API ports are already listening.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check prerequisites and print selected commands without starting processes.",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait before force killing processes on shutdown. 0 means wait indefinitely.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        names = resolve_profiles(args.profiles)
        specs = process_specs(
            names,
            pre_worker_name=args.pre_worker_name,
            post_worker_name=args.post_worker_name,
            solver_worker_name=args.solver_worker_name,
            pre_reload=not args.no_pre_reload,
        )
        check_prerequisites(specs, allow_used_ports=args.allow_used_ports)
    except RuntimeError as exc:
        print(f"[dev] error: {exc}", file=sys.stderr)
        return 2

    if args.check_only:
        print("[dev] selected processes:")
        for spec in specs:
            port = f" port={spec.port}" if spec.port is not None else ""
            env = ""
            if spec.env:
                env = " env=" + " ".join(f"{key}={value}" for key, value in sorted(spec.env.items()))
            print(f"[dev] - {spec.name}:{port} cwd={spec.cwd}{env} command={' '.join(spec.command)}")
        return 0

    return run_processes(specs, shutdown_timeout_seconds=max(args.shutdown_timeout, 0.0))


if __name__ == "__main__":
    raise SystemExit(main())

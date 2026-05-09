from __future__ import annotations

from collections import deque
from datetime import datetime, UTC
import json
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.logging_config import LOGGABLE_SERVICES, get_logs_root, log_file_path
from app.models.user import User


router = APIRouter(prefix="/logs", tags=["Logs"])

_WORKER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


@router.get("/services")
def list_log_services(
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    root = get_logs_root()
    services: list[dict[str, Any]] = []
    for service in LOGGABLE_SERVICES:
        service_dir = root / service
        workers = []
        if service_dir.exists():
            for path in sorted(service_dir.glob("*.jsonl")):
                workers.append(_file_summary(path, service=service))
        services.append({"service": service, "workers": workers})
    return {"logs_root": str(root), "services": services}


@router.get("/{service}/tail")
def tail_log_file(
    service: str,
    worker_name: str | None = None,
    lines: int = Query(default=300, ge=1, le=2000),
    q: str | None = Query(default=None, max_length=255),
    level: str | None = Query(default=None, max_length=31),
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    normalized_service = _validate_service(service)
    normalized_worker = _validate_worker_name(worker_name or normalized_service)
    path = log_file_path(service=normalized_service, worker_name=normalized_worker)
    if not path.exists():
        return {
            "service": normalized_service,
            "worker_name": normalized_worker,
            "file_path": str(path),
            "entries": [],
            "missing": True,
        }

    raw_lines = _tail_lines(path, lines=lines)
    entries = [_parse_log_line(line) for line in raw_lines]
    if level:
        expected_level = level.strip().upper()
        entries = [
            entry for entry in entries
            if str(entry.get("level") or "").upper() == expected_level
        ]
    if q:
        needle = q.strip().lower()
        entries = [
            entry for entry in entries
            if needle in json.dumps(entry, ensure_ascii=False, default=str).lower()
        ]

    return {
        "service": normalized_service,
        "worker_name": normalized_worker,
        "file_path": str(path),
        "entries": entries,
        "missing": False,
    }


@router.delete("/{service}")
def clear_log_file(
    service: str,
    worker_name: str | None = None,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    normalized_service = _validate_service(service)
    normalized_worker = _validate_worker_name(worker_name or normalized_service)
    path = log_file_path(service=normalized_service, worker_name=normalized_worker)
    existed = path.exists()
    previous_size_bytes = path.stat().st_size if existed else 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear log file: {exc}",
        ) from exc

    return {
        "service": normalized_service,
        "worker_name": normalized_worker,
        "file_path": str(path),
        "cleared": True,
        "existed": existed,
        "previous_size_bytes": previous_size_bytes,
    }


def _validate_service(service: str) -> str:
    normalized = service.strip().lower()
    if normalized not in LOGGABLE_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log service '{service}' is not available.",
        )
    return normalized


def _validate_worker_name(worker_name: str) -> str:
    normalized = worker_name.strip()
    if not _WORKER_NAME_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid worker_name.",
        )
    return normalized


def _file_summary(path: Path, *, service: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "service": service,
        "worker_name": path.stem,
        "file_name": path.name,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def _tail_lines(path: Path, *, lines: int) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n") for line in deque(handle, maxlen=lines)]


def _parse_log_line(line: str) -> dict[str, Any]:
    try:
        payload = json.loads(line)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return {"message": line, "raw": True}

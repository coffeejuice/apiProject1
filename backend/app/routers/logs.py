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
        entries = [entry for entry in entries if _entry_matches_query(entry, q)]

    return {
        "service": normalized_service,
        "worker_name": normalized_worker,
        "file_path": str(path),
        "entries": entries,
        "missing": False,
    }


@router.get("/{service}/related")
def related_log_records(
    service: str,
    worker_name: str | None = None,
    lines: int = Query(default=2000, ge=1, le=10000),
    limit: int = Query(default=20, ge=1, le=200),
    q: str | None = Query(default=None, max_length=255),
    level: str | None = Query(default=None, max_length=31),
    document_operation_id: int | None = None,
    document_version_id: int | None = None,
    execution_order: int | None = None,
    operation_template_id: str | None = Query(default=None, max_length=255),
    source_block_id: str | None = Query(default=None, max_length=255),
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    normalized_service = _validate_service(service)
    normalized_worker = _validate_worker_name(worker_name) if worker_name else None
    paths = _candidate_log_paths(service=normalized_service, worker_name=normalized_worker)
    expected_level = level.strip().upper() if level else None
    q_tokens = _query_tokens(q)
    search_terms = _related_search_terms(
        document_operation_id=document_operation_id,
        document_version_id=document_version_id,
        execution_order=execution_order,
        operation_template_id=operation_template_id,
        source_block_id=source_block_id,
    )

    related_entries: list[dict[str, Any]] = []
    missing_workers: list[str] = []
    for path in paths:
        worker = path.stem
        if not path.exists():
            missing_workers.append(worker)
            continue
        for raw_line in _tail_lines(path, lines=lines):
            entry = _parse_log_line(raw_line)
            if expected_level and str(entry.get("level") or "").upper() != expected_level:
                continue
            if q_tokens and not _entry_matches_tokens(entry, q_tokens):
                continue
            match_reasons = _related_match_reasons(entry, search_terms)
            if not match_reasons and search_terms:
                continue
            if not match_reasons and q_tokens:
                match_reasons = [f"q:{token}" for token in q_tokens]
            if not match_reasons:
                continue
            related_entries.append(
                {
                    "service": normalized_service,
                    "worker_name": worker,
                    "file_path": str(path),
                    "match_reasons": match_reasons,
                    "entry": entry,
                }
            )

    return {
        "service": normalized_service,
        "worker_name": normalized_worker,
        "searched_workers": [path.stem for path in paths],
        "missing_workers": missing_workers,
        "search": {
            "terms": search_terms,
            "q_tokens": q_tokens,
            "level": expected_level,
            "lines": lines,
            "limit": limit,
            "match_mode": "document_operation_id is primary; other provided fields are supporting evidence",
        },
        "entries": related_entries[-limit:],
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


def _candidate_log_paths(*, service: str, worker_name: str | None) -> list[Path]:
    if worker_name:
        return [log_file_path(service=service, worker_name=worker_name)]
    service_dir = get_logs_root() / service
    if not service_dir.exists():
        return [log_file_path(service=service, worker_name=service)]
    paths = sorted(service_dir.glob("*.jsonl"))
    return paths if paths else [log_file_path(service=service, worker_name=service)]


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


def _query_tokens(query: str | None) -> list[str]:
    if not query:
        return []
    return [
        token.strip().strip('"').strip("'").lower()
        for token in re.findall(r'"[^"]+"|' + r"'[^']+'" + r"|\S+", query)
        if token.strip().strip('"').strip("'")
    ]


def _entry_text(entry: dict[str, Any]) -> str:
    return json.dumps(entry, ensure_ascii=False, default=str).lower()


def _entry_matches_tokens(entry: dict[str, Any], tokens: list[str]) -> bool:
    text = _entry_text(entry)
    return all(token in text for token in tokens)


def _entry_matches_query(entry: dict[str, Any], query: str) -> bool:
    tokens = _query_tokens(query)
    return not tokens or _entry_matches_tokens(entry, tokens)


def _related_search_terms(
    *,
    document_operation_id: int | None,
    document_version_id: int | None,
    execution_order: int | None,
    operation_template_id: str | None,
    source_block_id: str | None,
) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    for key, value in (
        ("document_operation_id", document_operation_id),
        ("document_version_id", document_version_id),
        ("execution_order", execution_order),
        ("operation_template_id", operation_template_id),
        ("source_block_id", source_block_id),
    ):
        if value is None or value == "":
            continue
        terms.append({"key": key, "value": str(value)})
    return terms


def _related_match_reasons(entry: dict[str, Any], terms: list[dict[str, str]]) -> list[str]:
    if not terms:
        return []
    # document_operation_id is the stable row-level key. If it is present in
    # the search, require it to avoid noisy matches by template or document.
    primary_term = next((term for term in terms if term["key"] == "document_operation_id"), None)
    if primary_term and not _entry_has_term(entry, primary_term["key"], primary_term["value"]):
        return []

    reasons = [
        f"{term['key']}={term['value']}"
        for term in terms
        if _entry_has_term(entry, term["key"], term["value"])
    ]
    return reasons


def _entry_has_term(entry: dict[str, Any], key: str, value: str) -> bool:
    raw_value = entry.get(key)
    if raw_value is not None and str(raw_value) == value:
        return True
    text = _entry_text(entry)
    return (
        f"{key}={value}".lower() in text
        or f'"{key}": {json.dumps(value).lower()}' in text
        or f'"{key}": {value}'.lower() in text
    )

"""Local structured logging configuration for API and worker processes."""

from __future__ import annotations

from datetime import datetime, UTC
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import socket
from typing import Any

from app.config import settings


LOGGABLE_SERVICES = ("frontend", "api", "pre", "post", "solver", "coordinator")
_HOSTNAME = socket.gethostname()
_STANDARD_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


def get_logs_root() -> Path:
    """Return a writable log root, falling back to backend/logs for local dev."""

    configured_root = Path(settings.LOGS_FILES_ROOT).expanduser()
    try:
        configured_root.mkdir(parents=True, exist_ok=True)
        probe_path = configured_root / ".forgelab-write-test"
        probe_path.write_text("", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        return configured_root
    except OSError:
        fallback_root = Path(__file__).resolve().parents[1] / "logs"
        fallback_root.mkdir(parents=True, exist_ok=True)
        return fallback_root


def log_file_path(*, service: str, worker_name: str | None = None) -> Path:
    normalized_service = service.strip().lower()
    normalized_worker = (worker_name or normalized_service).strip() or normalized_service
    return get_logs_root() / normalized_service / f"{normalized_worker}.jsonl"


class JsonLineFormatter(logging.Formatter):
    """Small JSONL formatter avoiding an extra runtime dependency."""

    def __init__(self, *, service: str, worker_name: str) -> None:
        super().__init__()
        self.service = service
        self.worker_name = worker_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "worker_name": self.worker_name,
            "hostname": _HOSTNAME,
            "pid": record.process,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_KEYS or key in payload or key.startswith("_"):
                continue
            payload[key] = _json_safe(value)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(*, service: str, worker_name: str | None = None) -> Path | None:
    """Attach one rotating JSONL file handler for a supported local service."""

    normalized_service = service.strip().lower()
    if normalized_service not in LOGGABLE_SERVICES:
        return None

    normalized_worker = (worker_name or normalized_service).strip() or normalized_service
    path = log_file_path(service=normalized_service, worker_name=normalized_worker)
    path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    level = getattr(logging, settings.LOGGING_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(level)

    handler_key = f"forgelab:{normalized_service}:{normalized_worker}"
    for handler in root_logger.handlers:
        if getattr(handler, "_forgelab_handler_key", None) == handler_key:
            return path

    file_handler = RotatingFileHandler(
        path,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JsonLineFormatter(service=normalized_service, worker_name=normalized_worker))
    setattr(file_handler, "_forgelab_handler_key", handler_key)
    root_logger.addHandler(file_handler)
    logging.getLogger("app.logging").info(
        "Local file logging configured",
        extra={
            "event": "logging_configured",
            "log_file": str(path),
        },
    )
    return path


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    return str(value)

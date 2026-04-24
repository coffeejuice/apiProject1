"""LISTEN/NOTIFY helpers for runtime wake-up signaling."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
import logging
import re

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.config import settings


LOGGER = logging.getLogger(__name__)

_CHANNEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_channel_name(channel: str) -> str:
    """Reject channel names that cannot be safely used in LISTEN/UNLISTEN SQL."""

    if not _CHANNEL_RE.fullmatch(channel):
        raise ValueError(f"Invalid PostgreSQL channel name: {channel!r}")
    return channel


def _dedupe_channels(channels: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for channel in channels:
        seen[validate_channel_name(channel)] = None
    return tuple(seen)


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    """A normalized runtime notification emitted by PostgreSQL."""

    channel: str
    payload: str
    backend_pid: int


class PgNotifyListener:
    """Dedicated LISTEN/NOTIFY connection for coordinator and worker processes."""

    def __init__(self, channels: Sequence[str] = (), dsn: str | None = None) -> None:
        self._dsn = dsn or settings.DATABASE_URL
        self._channels = _dedupe_channels(channels)
        self._active_channels: tuple[str, ...] = ()
        self._conn: psycopg.Connection | None = None

    @property
    def channels(self) -> tuple[str, ...]:
        return self._channels

    def connect(self) -> psycopg.Connection:
        if self._conn is None:
            if not self._dsn:
                raise RuntimeError("DATABASE_URL is required for LISTEN/NOTIFY runtime")
            self._conn = psycopg.connect(_normalize_psycopg_dsn(self._dsn), autocommit=True)
            if self._channels:
                self._listen_on_connection(self._channels)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            with suppress(Exception):
                self._conn.close()
            self._conn = None
            self._active_channels = ()

    def __enter__(self) -> "PgNotifyListener":
        self.connect()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def listen(self, *channels: str) -> None:
        merged = _dedupe_channels((*self._channels, *channels))
        new_channels = [channel for channel in merged if channel not in self._active_channels]
        self.connect()
        if not new_channels:
            self._channels = merged
            return
        self._listen_on_connection(new_channels)
        self._channels = merged

    def unlisten(self, *channels: str) -> None:
        if self._conn is None:
            self._channels = tuple(
                channel for channel in self._channels if channel not in channels
            )
            return
        remove_channels = _dedupe_channels(channels)
        if not remove_channels:
            return
        with self._conn.cursor() as cursor:
            for channel in remove_channels:
                cursor.execute(
                    sql.SQL("UNLISTEN {};").format(sql.Identifier(channel))
                )
        self._active_channels = tuple(
            channel for channel in self._active_channels if channel not in remove_channels
        )
        self._channels = tuple(
            channel for channel in self._channels if channel not in remove_channels
        )

    def _listen_on_connection(self, channels: Iterable[str]) -> None:
        if self._conn is None:
            raise RuntimeError("LISTEN requires an open PostgreSQL connection")
        normalized_channels = _dedupe_channels(channels)
        if not normalized_channels:
            return
        with self._conn.cursor() as cursor:
            for channel in normalized_channels:
                cursor.execute(
                    sql.SQL("LISTEN {};").format(sql.Identifier(channel))
                )
        self._active_channels = _dedupe_channels(
            (*self._active_channels, *normalized_channels)
        )

    def wait(self, timeout: float | None = None, *, max_events: int = 64) -> list[NotificationEvent]:
        """Block until PostgreSQL delivers at least one event or the timeout expires."""

        if max_events < 1:
            return []
        conn = self.connect()
        first_batch = list(conn.notifies(timeout=timeout, stop_after=1))
        if not first_batch:
            return []

        notifications = list(first_batch)
        remaining = max_events - len(notifications)
        while remaining > 0:
            batch = list(conn.notifies(timeout=0.0, stop_after=remaining))
            if not batch:
                break
            notifications.extend(batch)
            remaining -= len(batch)

        return [
            NotificationEvent(
                channel=notification.channel,
                payload=notification.payload,
                backend_pid=notification.pid,
            )
            for notification in notifications
        ]


def send_notify(channel: str, payload: str = "", *, dsn: str | None = None) -> None:
    """Send a PostgreSQL notification on the given channel."""

    validated_channel = validate_channel_name(channel)
    dsn_value = dsn or settings.DATABASE_URL
    if not dsn_value:
        raise RuntimeError("DATABASE_URL is required to emit PostgreSQL notifications")
    with psycopg.connect(_normalize_psycopg_dsn(dsn_value), autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_notify(%s, %s);", (validated_channel, payload))


def broadcast_notify(
    channels: Iterable[str], payload: str = "", *, dsn: str | None = None
) -> None:
    """Emit the same payload to multiple channels on one connection."""

    dsn_value = dsn or settings.DATABASE_URL
    if not dsn_value:
        raise RuntimeError("DATABASE_URL is required to emit PostgreSQL notifications")
    normalized_channels = _dedupe_channels(channels)
    if not normalized_channels:
        return
    with psycopg.connect(_normalize_psycopg_dsn(dsn_value), autocommit=True) as conn:
        with conn.cursor() as cursor:
            for channel in normalized_channels:
                cursor.execute("SELECT pg_notify(%s, %s);", (channel, payload))
    LOGGER.debug("Broadcasted notify to channels=%s payload=%r", normalized_channels, payload)


def _normalize_psycopg_dsn(dsn: str) -> str:
    """Convert an SQLAlchemy PostgreSQL URL into a psycopg-compatible DSN."""

    if "+psycopg" not in dsn:
        return dsn
    return make_url(dsn).set(drivername="postgresql").render_as_string(hide_password=False)

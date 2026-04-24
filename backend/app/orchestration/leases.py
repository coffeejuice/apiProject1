"""Lease and heartbeat helpers for long-running worker jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Protocol

from app.config import settings


LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class LeasePolicy:
    """Timing policy for worker heartbeats and stale-lease recovery."""

    heartbeat_seconds: float = settings.WORKER_HEARTBEAT_SECONDS
    timeout_seconds: float = settings.WORKER_LEASE_TIMEOUT_SECONDS

    def next_expiry(self, *, now: datetime | None = None) -> datetime:
        reference = now or utc_now()
        return reference + timedelta(seconds=self.timeout_seconds)


@dataclass(slots=True)
class LeaseHeartbeat:
    """A single emitted heartbeat for one claimed job."""

    worker_name: str
    job_id: int | str
    recorded_at: datetime = field(default_factory=utc_now)


class LeaseManager(Protocol):
    """Adapter for runtime lease persistence and stale-claim recovery."""

    def heartbeat(self, heartbeat: LeaseHeartbeat) -> None:
        """Persist a heartbeat for the currently running job."""

    def recover_stale_claims(self) -> int:
        """Requeue or otherwise recover claims owned by dead workers."""


class NoopLeaseManager:
    """Placeholder lease manager used until orchestration tables exist."""

    def heartbeat(self, heartbeat: LeaseHeartbeat) -> None:
        LOGGER.debug(
            "Skipping heartbeat for worker=%s job_id=%s because no lease backend is configured",
            heartbeat.worker_name,
            heartbeat.job_id,
        )

    def recover_stale_claims(self) -> int:
        LOGGER.debug("Skipping stale-claim recovery because no lease backend is configured")
        return 0

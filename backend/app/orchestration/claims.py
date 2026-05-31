"""Database job-claiming helpers for self-claiming workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Protocol

from app.orchestration.state_machine import WorkflowStage


LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ClaimedStageJob:
    """A normalized unit of work claimed by a stage worker."""

    job_id: int | str
    stage: WorkflowStage
    worker_name: str
    run_id: int | str | None = None
    priority: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    claimed_at: datetime = field(default_factory=utc_now)
    lease_expires_at: datetime | None = None


class StageJobClaimer(Protocol):
    """Stage-specific adapter that claims the next runnable DB-backed job."""

    def claim_next_job(self, *, worker_name: str) -> ClaimedStageJob | None:
        """Return the next claimed job or ``None`` if nothing is eligible."""


class StageJobExecutor(Protocol):
    """Stage-specific execution adapter used by thin workers."""

    def execute(self, job: ClaimedStageJob) -> None:
        """Run one claimed job and persist its results."""


class NoopStageJobClaimer:
    """Placeholder claimer used until stage tables are wired to real SQL."""

    def claim_next_job(self, *, worker_name: str) -> ClaimedStageJob | None:
        LOGGER.debug("No claim backend configured yet for worker=%s", worker_name)
        return None


class LoggingStageJobExecutor:
    """Stub executor that keeps worker entrypoints runnable during migration."""

    def __init__(self, stage: WorkflowStage) -> None:
        self._stage = stage

    def execute(self, job: ClaimedStageJob) -> None:
        LOGGER.info(
            "Stub %s executor received job_id=%s run_id=%s priority=%s",
            self._stage,
            job.job_id,
            job.run_id,
            job.priority,
        )

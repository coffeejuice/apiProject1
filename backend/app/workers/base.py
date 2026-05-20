"""Shared worker types and bootstrap helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import logging
import signal
import time
from types import FrameType
from typing import Generic, TypeVar

from app.config import settings
from app.orchestration.leases import LeaseManager, NoopLeaseManager
from app.orchestration.pg_notify import NotificationEvent, PgNotifyListener


LOGGER = logging.getLogger(__name__)
WORKER_ERROR_BACKOFF_SECONDS = 2.0


class WorkerRole(StrEnum):
    """Supported long-running worker roles."""

    COORDINATOR = "coordinator"
    PRE = "pre"
    SOLVER = "solver"
    POST = "post"


@dataclass(slots=True)
class WorkerConfig:
    """Minimal runtime identity for a worker process."""

    role: WorkerRole
    instance_name: str


class ShutdownFlag:
    """Simple signal-backed stop flag for long-running worker processes."""

    def __init__(self) -> None:
        self._stop_requested = False

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    def install(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        LOGGER.info("Received shutdown signal=%s", signum)
        self._stop_requested = True


TJob = TypeVar("TJob")


class WorkerProcess(Generic[TJob], ABC):
    """Shared long-running loop for self-claiming workers."""

    def __init__(
        self,
        config: WorkerConfig,
        *,
        channel: str,
        listener: PgNotifyListener | None = None,
        lease_manager: LeaseManager | None = None,
        notify_timeout_seconds: float = settings.WORKER_NOTIFY_TIMEOUT_SECONDS,
    ) -> None:
        self.config = config
        self.channel = channel
        self._listener = listener or PgNotifyListener((channel,))
        self._lease_manager = lease_manager or NoopLeaseManager()
        self._notify_timeout_seconds = notify_timeout_seconds
        self._stop_flag: ShutdownFlag | None = None

    def run(self) -> None:
        stop_flag = ShutdownFlag()
        self._stop_flag = stop_flag
        stop_flag.install()

        try:
            with self._listener as listener:
                listener.listen(self.channel)
                LOGGER.info(
                    "Worker started role=%s instance=%s channel=%s",
                    self.config.role,
                    self.config.instance_name,
                    self.channel,
                )

                while not stop_flag.stop_requested:
                    processed = self._drain_claimable_jobs()
                    if stop_flag.stop_requested:
                        break
                    if processed:
                        continue

                    try:
                        recovered = self._lease_manager.recover_stale_claims()
                    except Exception:
                        LOGGER.exception(
                            "Worker stale-claim recovery failed role=%s instance=%s; worker stays alive",
                            self.config.role,
                            self.config.instance_name,
                        )
                        time.sleep(WORKER_ERROR_BACKOFF_SECONDS)
                        continue
                    if recovered:
                        LOGGER.info(
                            "Recovered stale claims role=%s count=%s",
                            self.config.role,
                            recovered,
                        )
                        continue

                    try:
                        notifications = listener.wait(timeout=self._notify_timeout_seconds)
                    except Exception:
                        LOGGER.exception(
                            "Worker notification wait failed role=%s instance=%s; worker stays alive",
                            self.config.role,
                            self.config.instance_name,
                        )
                        time.sleep(WORKER_ERROR_BACKOFF_SECONDS)
                        continue
                    if notifications:
                        try:
                            self.handle_notifications(notifications)
                        except Exception:
                            LOGGER.exception(
                                "Worker notification handler failed role=%s instance=%s; worker stays alive",
                                self.config.role,
                                self.config.instance_name,
                            )
        finally:
            self._stop_flag = None

        LOGGER.info("Worker stopped role=%s instance=%s", self.config.role, self.config.instance_name)

    def _drain_claimable_jobs(self) -> int:
        processed = 0
        while True:
            if self._stop_flag is not None and self._stop_flag.stop_requested:
                return processed
            try:
                job = self.claim_next_job()
            except Exception:
                LOGGER.exception(
                    "Worker job claim failed role=%s instance=%s; worker stays alive",
                    self.config.role,
                    self.config.instance_name,
                )
                time.sleep(WORKER_ERROR_BACKOFF_SECONDS)
                return processed
            if job is None:
                return processed
            try:
                self.process_job(job)
            except Exception as exc:
                LOGGER.exception(
                    "Worker job failed unexpectedly role=%s instance=%s job_id=%s; worker stays alive",
                    self.config.role,
                    self.config.instance_name,
                    getattr(job, "job_id", None),
                )
                try:
                    self.handle_job_error(job, exc)
                except Exception:
                    LOGGER.exception(
                        "Worker failed to persist job failure role=%s instance=%s job_id=%s",
                        self.config.role,
                        self.config.instance_name,
                        getattr(job, "job_id", None),
                    )
            processed += 1

    def handle_notifications(self, notifications: list[NotificationEvent]) -> None:
        """Hook for lightweight logging or custom wake-up behavior."""

        LOGGER.debug(
            "Worker wake-up role=%s instance=%s notifications=%s",
            self.config.role,
            self.config.instance_name,
            [(event.channel, event.payload) for event in notifications],
        )

    def handle_job_error(self, job: TJob, exc: Exception) -> None:
        """Persist stage-specific failure state after an unexpected job error.

        Subclasses can override this hook. The base loop deliberately treats
        job exceptions as data/job failures, not worker-process failures.
        """

        LOGGER.debug("No stage-specific job error handler configured for job=%s error=%s", job, exc)

    @abstractmethod
    def claim_next_job(self) -> TJob | None:
        """Claim the next eligible job for this worker."""

    @abstractmethod
    def process_job(self, job: TJob) -> None:
        """Run the claimed job."""

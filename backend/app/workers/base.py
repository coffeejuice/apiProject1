"""Shared worker types and bootstrap helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import logging
import signal
from types import FrameType
from typing import Generic, TypeVar

from app.config import settings
from app.orchestration.leases import LeaseManager, NoopLeaseManager
from app.orchestration.pg_notify import NotificationEvent, PgNotifyListener


LOGGER = logging.getLogger(__name__)


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

    def run(self) -> None:
        stop_flag = ShutdownFlag()
        stop_flag.install()

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

                recovered = self._lease_manager.recover_stale_claims()
                if recovered:
                    LOGGER.info(
                        "Recovered stale claims role=%s count=%s",
                        self.config.role,
                        recovered,
                    )
                    continue

                notifications = listener.wait(timeout=self._notify_timeout_seconds)
                if notifications:
                    self.handle_notifications(notifications)

        LOGGER.info("Worker stopped role=%s instance=%s", self.config.role, self.config.instance_name)

    def _drain_claimable_jobs(self) -> int:
        processed = 0
        while True:
            job = self.claim_next_job()
            if job is None:
                return processed
            self.process_job(job)
            processed += 1

    def handle_notifications(self, notifications: list[NotificationEvent]) -> None:
        """Hook for lightweight logging or custom wake-up behavior."""

        LOGGER.debug(
            "Worker wake-up role=%s instance=%s notifications=%s",
            self.config.role,
            self.config.instance_name,
            [(event.channel, event.payload) for event in notifications],
        )

    @abstractmethod
    def claim_next_job(self) -> TJob | None:
        """Claim the next eligible job for this worker."""

    @abstractmethod
    def process_job(self, job: TJob) -> None:
        """Run the claimed job."""

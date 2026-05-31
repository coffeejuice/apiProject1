"""Thin workflow coordinator entrypoint and reconciliation logic."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import signal
from types import FrameType
from typing import Protocol

from app.config import settings
from app.logging_config import configure_logging
from app.orchestration.channels import WORKFLOW_EVENTS_CHANNEL
from app.orchestration.leases import LeaseManager
from app.orchestration.pg_notify import PgNotifyListener
from app.orchestration.runtime_backend import DatabaseCoordinatorHooks, SqlAlchemyLeaseManager
from app.workers.base import WorkerConfig, WorkerRole


LOGGER = logging.getLogger(__name__)


class CoordinatorHooks(Protocol):
    """Cross-stage reconciliation hooks owned by the workflow coordinator."""

    def recover_stale_claims(self) -> int:
        """Recover claims owned by dead or disconnected workers."""

    def reconcile_pre_jobs(self) -> int:
        """Coalesce document changes into runnable preprocessing jobs."""

    def advance_solver_pipeline(self) -> int:
        """Open next solver-step jobs for eligible runs."""

    def enqueue_post_jobs(self) -> int:
        """Create postprocessing jobs from finished solver-step outputs."""

    def sync_workflow_statuses(self) -> int:
        """Update aggregate workflow/document/run status values."""


@dataclass(slots=True)
class NoopCoordinatorHooks:
    """Placeholder coordinator hooks used until DB tables are added."""

    def recover_stale_claims(self) -> int:
        return 0

    def reconcile_pre_jobs(self) -> int:
        return 0

    def advance_solver_pipeline(self) -> int:
        return 0

    def enqueue_post_jobs(self) -> int:
        return 0

    def sync_workflow_statuses(self) -> int:
        return 0


class WorkflowCoordinator:
    """Lightweight reconciler that advances persisted workflow state."""

    def __init__(
        self,
        config: WorkerConfig,
        *,
        hooks: CoordinatorHooks | None = None,
        lease_manager: LeaseManager | None = None,
        notify_timeout_seconds: float = settings.WORKER_NOTIFY_TIMEOUT_SECONDS,
    ) -> None:
        self.config = config
        self._hooks = hooks or DatabaseCoordinatorHooks()
        self._lease_manager = lease_manager or SqlAlchemyLeaseManager()
        self._notify_timeout_seconds = notify_timeout_seconds
        self._stop_requested = False

    def run(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        with PgNotifyListener((WORKFLOW_EVENTS_CHANNEL,)) as listener:
            LOGGER.info(
                "Coordinator started instance=%s channel=%s",
                self.config.instance_name,
                WORKFLOW_EVENTS_CHANNEL,
            )
            while not self._stop_requested:
                changed = self.reconcile_once()
                if changed:
                    continue
                listener.wait(timeout=self._notify_timeout_seconds)
            LOGGER.info("Coordinator stopped instance=%s", self.config.instance_name)

    def reconcile_once(self) -> int:
        """Run one idempotent reconciliation pass and return number of changes."""

        operations = (
            self._lease_manager.recover_stale_claims,
            self._hooks.recover_stale_claims,
            self._hooks.reconcile_pre_jobs,
            self._hooks.advance_solver_pipeline,
            self._hooks.enqueue_post_jobs,
            self._hooks.sync_workflow_statuses,
        )
        changes = 0
        for operation in operations:
            changes += operation()
        if changes:
            LOGGER.info(
                "Coordinator reconciliation changed persisted workflow state count=%s",
                changes,
            )
        return changes

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        LOGGER.info("Coordinator received shutdown signal=%s", signum)
        self._stop_requested = True


def main() -> None:
    """Start the workflow coordinator process."""

    instance_name = os.getenv("FORGELAB_WORKER_NAME", "coordinator-1")
    configure_logging(service="coordinator", worker_name=instance_name)
    coordinator = WorkflowCoordinator(
        WorkerConfig(role=WorkerRole.COORDINATOR, instance_name=instance_name),
    )
    coordinator.run()


if __name__ == "__main__":
    main()

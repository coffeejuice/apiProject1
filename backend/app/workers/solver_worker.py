"""Solver worker entrypoint."""

from __future__ import annotations

import logging
import os

from app.orchestration.channels import SOLVER_JOBS_CHANNEL
from app.orchestration.claims import ClaimedStageJob, StageJobClaimer, StageJobExecutor
from app.orchestration.runtime_backend import SolverJobClaimer, SolverJobExecutor, SqlAlchemyLeaseManager
from app.workers.base import WorkerConfig, WorkerProcess, WorkerRole


LOGGER = logging.getLogger(__name__)


class SolverWorker(WorkerProcess[ClaimedStageJob]):
    """Thin runtime shell for single-step solver jobs."""

    def __init__(
        self,
        config: WorkerConfig,
        *,
        claimer: StageJobClaimer | None = None,
        executor: StageJobExecutor | None = None,
    ) -> None:
        super().__init__(config, channel=SOLVER_JOBS_CHANNEL, lease_manager=SqlAlchemyLeaseManager())
        self._claimer = claimer or SolverJobClaimer()
        self._executor = executor or SolverJobExecutor()

    def claim_next_job(self) -> ClaimedStageJob | None:
        return self._claimer.claim_next_job(worker_name=self.config.instance_name)

    def process_job(self, job: ClaimedStageJob) -> None:
        LOGGER.info("Processing solver job_id=%s", job.job_id)
        self._executor.execute(job)


def main() -> None:
    """Start the solver worker process."""

    instance_name = os.getenv("FORGELAB_WORKER_NAME", "solver-1")
    worker = SolverWorker(
        WorkerConfig(role=WorkerRole.SOLVER, instance_name=instance_name),
    )
    worker.run()


if __name__ == "__main__":
    main()

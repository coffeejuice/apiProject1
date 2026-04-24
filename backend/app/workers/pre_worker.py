"""Pre worker entrypoint."""

from __future__ import annotations

import logging
import os

from app.orchestration.channels import PRE_JOBS_CHANNEL
from app.orchestration.claims import ClaimedStageJob, StageJobClaimer, StageJobExecutor
from app.orchestration.runtime_backend import PreJobClaimer, PreJobExecutor, SqlAlchemyLeaseManager
from app.workers.base import WorkerConfig, WorkerProcess, WorkerRole


LOGGER = logging.getLogger(__name__)


class PreWorker(WorkerProcess[ClaimedStageJob]):
    """Thin runtime shell for preprocessor jobs."""

    def __init__(
        self,
        config: WorkerConfig,
        *,
        claimer: StageJobClaimer | None = None,
        executor: StageJobExecutor | None = None,
    ) -> None:
        super().__init__(config, channel=PRE_JOBS_CHANNEL, lease_manager=SqlAlchemyLeaseManager())
        self._claimer = claimer or PreJobClaimer()
        self._executor = executor or PreJobExecutor()

    def claim_next_job(self) -> ClaimedStageJob | None:
        return self._claimer.claim_next_job(worker_name=self.config.instance_name)

    def process_job(self, job: ClaimedStageJob) -> None:
        LOGGER.info("Processing pre job_id=%s", job.job_id)
        self._executor.execute(job)


def main() -> None:
    """Start the pre worker process."""

    instance_name = os.getenv("FORGELAB_WORKER_NAME", "pre-1")
    worker = PreWorker(
        WorkerConfig(role=WorkerRole.PRE, instance_name=instance_name),
    )
    worker.run()


if __name__ == "__main__":
    main()

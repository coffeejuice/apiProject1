"""Workflow state transitions for pre, solver, and post stages."""

from __future__ import annotations

from enum import StrEnum


class WorkflowStage(StrEnum):
    """Execution stages owned by the new runtime."""

    PRE = "pre"
    SOLVER = "solver"
    POST = "post"


class StageJobStatus(StrEnum):
    """Persisted states for one runnable stage job."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class WorkflowRunStatus(StrEnum):
    """High-level status for an immutable queued document/run."""

    WAITING_PRE = "waiting_pre"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED_BETWEEN_STEPS = "paused_between_steps"
    FINISHED = "finished"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


_STAGE_TRANSITIONS: dict[StageJobStatus, frozenset[StageJobStatus]] = {
    StageJobStatus.QUEUED: frozenset(
        {StageJobStatus.CLAIMED, StageJobStatus.CANCEL_REQUESTED, StageJobStatus.CANCELLED}
    ),
    StageJobStatus.CLAIMED: frozenset(
        {StageJobStatus.RUNNING, StageJobStatus.QUEUED, StageJobStatus.FAILED}
    ),
    StageJobStatus.RUNNING: frozenset(
        {
            StageJobStatus.SUCCEEDED,
            StageJobStatus.FAILED,
            StageJobStatus.CANCEL_REQUESTED,
        }
    ),
    StageJobStatus.SUCCEEDED: frozenset(),
    StageJobStatus.FAILED: frozenset({StageJobStatus.QUEUED}),
    StageJobStatus.CANCEL_REQUESTED: frozenset(
        {StageJobStatus.CANCELLED, StageJobStatus.FAILED}
    ),
    StageJobStatus.CANCELLED: frozenset(),
}

_RUN_TRANSITIONS: dict[WorkflowRunStatus, frozenset[WorkflowRunStatus]] = {
    WorkflowRunStatus.WAITING_PRE: frozenset(
        {
            WorkflowRunStatus.QUEUED,
            WorkflowRunStatus.CANCEL_REQUESTED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.FAILED,
        }
    ),
    WorkflowRunStatus.QUEUED: frozenset(
        {
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.PAUSED_BETWEEN_STEPS,
            WorkflowRunStatus.CANCEL_REQUESTED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.FAILED,
        }
    ),
    WorkflowRunStatus.RUNNING: frozenset(
        {
            WorkflowRunStatus.PAUSED_BETWEEN_STEPS,
            WorkflowRunStatus.FINISHED,
            WorkflowRunStatus.CANCEL_REQUESTED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.FAILED,
        }
    ),
    WorkflowRunStatus.PAUSED_BETWEEN_STEPS: frozenset(
        {
            WorkflowRunStatus.QUEUED,
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.CANCEL_REQUESTED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.FAILED,
        }
    ),
    WorkflowRunStatus.FINISHED: frozenset(),
    WorkflowRunStatus.FAILED: frozenset({WorkflowRunStatus.QUEUED}),
    WorkflowRunStatus.CANCEL_REQUESTED: frozenset(
        {WorkflowRunStatus.CANCELLED, WorkflowRunStatus.FAILED}
    ),
    WorkflowRunStatus.CANCELLED: frozenset(),
}


def can_transition_stage(current: StageJobStatus, target: StageJobStatus) -> bool:
    """Return whether a stage-job transition is valid."""

    return target == current or target in _STAGE_TRANSITIONS[current]


def can_transition_run(current: WorkflowRunStatus, target: WorkflowRunStatus) -> bool:
    """Return whether a workflow-run transition is valid."""

    return target == current or target in _RUN_TRANSITIONS[current]


def assert_stage_transition(current: StageJobStatus, target: StageJobStatus) -> None:
    """Fail fast on invalid stage-job transitions."""

    if not can_transition_stage(current, target):
        raise ValueError(f"Invalid stage transition: {current} -> {target}")


def assert_run_transition(current: WorkflowRunStatus, target: WorkflowRunStatus) -> None:
    """Fail fast on invalid workflow-run transitions."""

    if not can_transition_run(current, target):
        raise ValueError(f"Invalid run transition: {current} -> {target}")


def next_stage(stage: WorkflowStage) -> WorkflowStage | None:
    """Return the next pipeline stage after the given stage."""

    if stage is WorkflowStage.PRE:
        return WorkflowStage.SOLVER
    if stage is WorkflowStage.SOLVER:
        return WorkflowStage.POST
    return None

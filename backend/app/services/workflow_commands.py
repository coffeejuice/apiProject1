"""User-command workflow business logic owned by the FastAPI layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document.document_operation import DocumentOperation
from app.models.document.document import Document, DocumentVersion, PreprocessStatus, SimulationStatus
from app.models.user import User, UserPriority
from app.orchestration.channels import PRE_JOBS_CHANNEL, WORKFLOW_EVENTS_CHANNEL
from app.orchestration.pg_notify import broadcast_notify
from app.services.block_service import create_block, get_ordered_blocks
from app.services.document_operations import regenerate_document_operations
from app.services.files.paths import generate_project_dir_name


LOGGER = logging.getLogger(__name__)


class WorkflowCommandError(ValueError):
    """Raised when a user command violates workflow business rules."""


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    """Derived workflow view for a document version."""

    workflow_state: str
    preprocess_requested: bool
    automation_active: bool
    document_fixed: bool


_DEFAULT_SIMULATION_PRIORITY_BY_USER_PRIORITY = {
    UserPriority.low: 8,
    UserPriority.normal: 5,
    UserPriority.high: 2,
}


def now_utc() -> datetime:
    """Return the timestamp used for workflow updates."""

    return datetime.utcnow()


def get_latest_document_version(db: Session, document_id: int) -> DocumentVersion | None:
    """Return the newest version row for one document."""

    return (
        db.execute(
            select(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.document_version_id.desc())
        )
        .scalars()
        .first()
    )


def get_document_version_or_none(db: Session, document_version_id: int) -> DocumentVersion | None:
    """Return one version row or ``None``."""

    return db.get(DocumentVersion, document_version_id)


def count_document_operations(db: Session, document_id: int) -> int:
    """Count materialized technological operations for workflow summaries."""

    return int(
        db.execute(
            select(func.count())
            .select_from(DocumentOperation)
            .filter(DocumentOperation.document_id == document_id)
        ).scalar()
        or 0
    )


def derive_simulation_priority(user_priority: UserPriority | None) -> int:
    """Return the numeric simulation priority used by queue ordering."""

    return _DEFAULT_SIMULATION_PRIORITY_BY_USER_PRIORITY.get(user_priority or UserPriority.normal, 5)


def build_workflow_snapshot(version: DocumentVersion | None) -> WorkflowSnapshot:
    """Derive workflow business state from the persisted version row."""

    if version is None:
        return WorkflowSnapshot(
            workflow_state="draft",
            preprocess_requested=False,
            automation_active=False,
            document_fixed=False,
        )

    preprocess_requested = bool(version.run_switch_status)
    automation_active = bool(version.run_switch_is_active)
    document_fixed = not bool(version.is_editable)

    if not document_fixed:
        workflow_state = "draft_waiting_pre" if preprocess_requested else "draft"
    elif version.simulation_status is SimulationStatus.run:
        workflow_state = "running"
    elif version.simulation_status is SimulationStatus.pause:
        workflow_state = "paused"
    elif version.simulation_status is SimulationStatus.done:
        workflow_state = "finished"
    elif version.simulation_status is SimulationStatus.error:
        workflow_state = "failed"
    elif automation_active and preprocess_requested:
        workflow_state = "waiting_pre"
    elif automation_active:
        workflow_state = "queued"
    else:
        workflow_state = "fixed"

    return WorkflowSnapshot(
        workflow_state=workflow_state,
        preprocess_requested=preprocess_requested,
        automation_active=automation_active,
        document_fixed=document_fixed,
    )


def is_document_fixed(db: Session, document_id: int) -> bool:
    """Return whether the current document is frozen and can no longer be edited."""

    version = get_latest_document_version(db, document_id)
    return bool(version is not None and version.is_editable is False)


def assert_document_editable(db: Session, document_id: int) -> None:
    """Reject modifications to documents that were already fixed for simulation."""

    if is_document_fixed(db, document_id):
        raise WorkflowCommandError(
            "Document is fixed and cannot be modified. Fork it to continue editing."
        )


def _sync_version_metadata(
    db: Session,
    version: DocumentVersion,
    *,
    document: Document,
) -> None:
    version.name = document.name
    version.operations_count = count_document_operations(db, document.document_id)
    version.last_modified = now_utc()


def ensure_editable_version(
    db: Session,
    document: Document,
    *,
    current_user: User | None = None,
    parent_version: DocumentVersion | None = None,
    create_if_missing: bool = True,
) -> DocumentVersion:
    """Return the current editable version or create one for a draft document."""

    version = get_latest_document_version(db, document.document_id)
    if version is not None:
        if version.is_editable is False:
            raise WorkflowCommandError(
                "Document is fixed and cannot be modified. Fork it to continue editing."
            )
        _sync_version_metadata(db, version, document=document)
        return version

    if not create_if_missing:
        raise WorkflowCommandError("Editable version does not exist for this document.")

    priority_enum = current_user.user_priority_enum if current_user is not None else UserPriority.normal
    version = DocumentVersion(
        document_id=document.document_id,
        parent_document_version_id=(
            parent_version.document_version_id if parent_version is not None else None
        ),
        is_editable=True,
        run_switch_status=False,
        run_switch_is_active=False,
        preprocess_status=PreprocessStatus.ready,
        simulation_status=SimulationStatus.stop,
        name=document.name,
        document_priority_enum=priority_enum,
        simulation_priority=derive_simulation_priority(priority_enum),
        operations_count=count_document_operations(db, document.document_id),
    )
    db.add(version)
    db.flush()
    version.project_dir_name = generate_project_dir_name(version.document_version_id)
    version.last_modified = now_utc()
    return version


def create_initial_working_version(
    db: Session,
    document: Document,
    *,
    current_user: User | None = None,
    parent_version: DocumentVersion | None = None,
    preprocess_requested: bool = False,
) -> DocumentVersion:
    """Create the first editable workflow version for a new draft document."""

    version = ensure_editable_version(
        db,
        document,
        current_user=current_user,
        parent_version=parent_version,
        create_if_missing=True,
    )
    version.run_switch_status = preprocess_requested
    version.run_switch_is_active = False
    version.preprocess_status = (
        PreprocessStatus.queued if preprocess_requested else PreprocessStatus.ready
    )
    version.preprocess_worker_name = None
    version.preprocess_started_at = None
    version.preprocess_finished_at = None
    version.preprocess_error = None
    version.simulation_status = SimulationStatus.stop
    version.last_modified = now_utc()
    return version


def mark_document_edited(
    db: Session,
    document: Document,
    *,
    current_user: User | None = None,
) -> DocumentVersion:
    """Record that user edits require fresh preprocessing for the current draft."""

    version = ensure_editable_version(db, document, current_user=current_user)
    version.run_switch_status = True
    version.run_switch_is_active = False
    version.preprocess_status = PreprocessStatus.queued
    version.preprocess_worker_name = None
    version.preprocess_started_at = None
    version.preprocess_finished_at = None
    version.preprocess_error = None
    version.simulation_status = SimulationStatus.stop
    version.simulation_percent = 0
    version.simulation_server_id = None
    version.finished_at = None
    version.ran_at = None
    version.last_modified = now_utc()
    document.updated_at = version.last_modified
    return version


def queue_document_for_simulation(
    db: Session,
    document: Document,
    *,
    current_user: User,
    simulation_priority: int | None = None,
    document_priority: UserPriority | None = None,
) -> DocumentVersion:
    """Freeze a draft document and activate automatic workflow handling for it."""

    version = ensure_editable_version(db, document, current_user=current_user)
    version.is_editable = False
    version.run_switch_is_active = True
    if version.run_switch_status:
        version.preprocess_status = PreprocessStatus.queued
    version.document_priority_enum = document_priority or current_user.user_priority_enum
    version.simulation_priority = (
        simulation_priority
        if simulation_priority is not None
        else derive_simulation_priority(version.document_priority_enum)
    )
    version.simulation_status = SimulationStatus.stop
    version.last_modified = now_utc()
    document.updated_at = version.last_modified
    return version


def update_run_priority(
    version: DocumentVersion,
    *,
    simulation_priority: int | None = None,
    document_priority: UserPriority | None = None,
) -> DocumentVersion:
    """Apply user-adjusted priority to an existing fixed workflow run."""

    if version.is_editable:
        raise WorkflowCommandError("Priority can only be changed for a fixed queued or running version.")
    if simulation_priority is not None:
        version.simulation_priority = simulation_priority
    if document_priority is not None:
        version.document_priority_enum = document_priority
    version.last_modified = now_utc()
    return version


def pause_run(version: DocumentVersion) -> DocumentVersion:
    """Record a user pause command for the coordinator to honor."""

    if version.is_editable:
        raise WorkflowCommandError("Editable draft versions cannot be paused.")
    if version.simulation_status is SimulationStatus.done:
        raise WorkflowCommandError("Finished runs cannot be paused.")
    version.run_switch_is_active = True
    version.simulation_status = SimulationStatus.pause
    version.last_modified = now_utc()
    return version


def resume_run(version: DocumentVersion) -> DocumentVersion:
    """Clear a user pause command and reactivate automation for the run."""

    if version.is_editable:
        raise WorkflowCommandError("Editable draft versions cannot be resumed.")
    if version.simulation_status is SimulationStatus.done:
        raise WorkflowCommandError("Finished runs cannot be resumed.")
    version.run_switch_is_active = True
    if version.simulation_status is SimulationStatus.pause:
        version.simulation_status = SimulationStatus.stop
    version.last_modified = now_utc()
    return version


def cancel_run(version: DocumentVersion) -> DocumentVersion:
    """Deactivate automation for a fixed workflow run."""

    if version.is_editable:
        raise WorkflowCommandError("Editable draft versions cannot be cancelled.")
    if version.simulation_status is SimulationStatus.done:
        raise WorkflowCommandError("Finished runs cannot be cancelled.")
    version.run_switch_is_active = False
    version.simulation_status = SimulationStatus.stop
    version.simulation_server_id = None
    version.last_modified = now_utc()
    return version


def retry_run(version: DocumentVersion) -> DocumentVersion:
    """Retry a failed or stopped fixed run."""

    if version.is_editable:
        raise WorkflowCommandError("Editable draft versions cannot be retried.")
    if version.simulation_status not in {SimulationStatus.error, SimulationStatus.stop, SimulationStatus.pause}:
        raise WorkflowCommandError("Only failed, paused, or stopped runs can be retried.")
    version.run_switch_is_active = True
    if version.run_switch_status:
        version.preprocess_status = PreprocessStatus.queued
    version.simulation_status = SimulationStatus.stop
    version.simulation_percent = 0
    version.simulation_server_id = None
    version.ran_at = None
    version.finished_at = None
    version.last_modified = now_utc()
    return version


def fork_fixed_document(
    db: Session,
    source_document: Document,
    *,
    name: str,
    notes: str | None,
    editor_user_id: int | None,
    current_user: User,
) -> Document:
    """Create an editable fork from a fixed source document."""

    source_version = get_latest_document_version(db, source_document.document_id)
    if source_version is None or source_version.is_editable:
        raise WorkflowCommandError("Only fixed documents can be forked.")

    forked = Document(
        project_id=source_document.project_id,
        source_document_id=source_document.document_id,
        editor_user_id=editor_user_id or source_document.editor_user_id or current_user.user_id,
        material_version_id=source_document.material_version_id,
        name=name,
        notes=notes if notes is not None else source_document.notes,
    )
    db.add(forked)
    db.flush()

    previous_new_id = None
    for source_block in get_ordered_blocks(db, source_document.document_id):
        created = create_block(
            db=db,
            document_id=forked.document_id,
            block_type_id=source_block.block_type_id,
            props=dict(source_block.props or {}),
            previous_block_id=previous_new_id,
            is_system=source_block.is_system,
            is_removable=source_block.is_removable,
            fixed_position=source_block.fixed_position,
        )
        previous_new_id = created.block_id

    regenerate_document_operations(db, forked.document_id)
    create_initial_working_version(
        db,
        forked,
        current_user=current_user,
        parent_version=source_version,
        preprocess_requested=count_document_operations(db, forked.document_id) > 0,
    )
    forked.updated_at = now_utc()
    return forked


def emit_workflow_notifications(channels: Iterable[str]) -> None:
    """Wake coordinator and workers after a committed user command."""

    try:
        broadcast_notify(tuple(channels), payload="wake")
    except Exception:
        LOGGER.exception("Failed to broadcast workflow notifications")


def notify_after_edit() -> None:
    """Emit notifications for document edits that require preprocessing."""

    emit_workflow_notifications((WORKFLOW_EVENTS_CHANNEL, PRE_JOBS_CHANNEL))


def notify_after_run_command() -> None:
    """Emit notifications for queue/priority/pause/resume/cancel/retry commands."""

    emit_workflow_notifications((WORKFLOW_EVENTS_CHANNEL, PRE_JOBS_CHANNEL))

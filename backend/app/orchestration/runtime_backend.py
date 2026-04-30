"""DB-backed coordinator and worker runtime adapters."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import socket
from typing import Iterable

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document.block import Block
from app.models.document.document import (
    Document,
    DocumentVersion,
    PreprocessStatus,
    SimulationStatus,
)
from app.models.document.document_operation import DocumentOperation
from app.models.library.material import MaterialVersion
from app.models.project import Project
from app.models.server import Server, ServerType
from app.models.workflow_runtime import (
    PostprocessingTask,
    PostprocessingTaskStatusEnum,
    SimulationStep,
    SimulationStepStatus,
    SimulationStepStatusEnum,
)
from app.orchestration.channels import (
    POST_JOBS_CHANNEL,
    PRE_JOBS_CHANNEL,
    SOLVER_JOBS_CHANNEL,
    WORKFLOW_EVENTS_CHANNEL,
)
from app.orchestration.claims import ClaimedStageJob, StageJobClaimer, StageJobExecutor
from app.orchestration.leases import LeaseHeartbeat, LeaseManager, LeasePolicy
from app.orchestration.pg_notify import broadcast_notify
from app.orchestration.state_machine import WorkflowStage
from app.services.block_props import (
    DOCUMENT_PROPERTIES,
    OPERATION_PROPERTIES,
    extract_namespace,
    normalize_document_block_props,
)
from app.services.block_service import get_ordered_blocks
from app.services.document_operations import regenerate_document_operations
from app.services.operation_blocks import OPERATION_BLOCK_TYPE_ID, operation_target_to_parameters
from app.services.preprocessor.compiler import (
    CompiledControlProgram,
    CompiledControlProgramRow,
    PreprocessorCompiler,
    PreprocessorCompileError,
    ProcessCard,
)
from app.services.preprocessor.geometry import GeneratedGeometry


LOGGER = logging.getLogger(__name__)

DEFAULT_MATERIAL_DENSITY_KG_PER_MM3 = 7.85e-6


def now_utc() -> datetime:
    return datetime.utcnow()


@contextmanager
def session_scope() -> Iterable[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _resolve_server_id(session: Session, *, worker_name: str, server_type: ServerType) -> int | None:
    hostname = socket.gethostname()
    stmt = (
        select(Server.id)
        .where(
            Server.type == server_type,
            or_(Server.name == worker_name, Server.hostname == hostname),
        )
        .order_by(case((Server.name == worker_name, 0), else_=1), Server.id.asc())
    )
    return session.execute(stmt).scalar()


def _serialize_geometry(geometry: GeneratedGeometry | None) -> dict[str, object] | None:
    if geometry is None:
        return None
    return {
        "type_id": geometry.type_id,
        "shape": geometry.shape,
        "parameters": dict(geometry.parameters),
        "volume_mm3": geometry.volume_mm3,
        "cross_section_area_mm2": geometry.cross_section_area_mm2,
        "equivalent_diameter_mm": geometry.equivalent_diameter_mm,
        "width_mm": geometry.width_mm,
        "height_mm": geometry.height_mm,
        "length_mm": geometry.length_mm,
        "cross_section_outline": [[point[0], point[1]] for point in geometry.cross_section_outline],
        "parameters_json": geometry.parameters_json,
    }


def _compiled_row_to_step_payload(
    row: CompiledControlProgramRow,
    *,
    material_version_id: int | None,
) -> dict[str, object]:
    duration_seconds = float(row.duration_seconds or 0.0)
    stop_seconds = float(row.total_time_seconds or 0.0)
    start_seconds = max(0.0, stop_seconds - duration_seconds)
    metrics = dict(row.metrics or {})
    metrics.update(
        {
            "operation_id": row.operation_id,
            "operation_type": row.operation_type,
            "deformation_control": row.deformation_control,
            "step_control": row.step_control,
            "temperature_initial_c": row.temperature_initial_c,
            "temperature_final_c": row.temperature_final_c,
            "initial_surface_area_mm2": row.initial_surface_area_mm2,
            "final_surface_area_mm2": row.final_surface_area_mm2,
            "compiler_notes": list(row.compiler_notes),
            "material_label": row.material_label,
            "weight_kg": row.weight_kg,
        }
    )
    step_specific_parameters = dict(row.operation_specific_parameters or {})
    step_specific_parameters.update(
        {
            "operation_id": row.operation_id,
            "operation_type": row.operation_type,
            "deformation_control": row.deformation_control,
            "step_control": row.step_control,
            "simulation_index": row.simulation_index,
        }
    )
    return {
        "document_operation_id": row.document_operation_id,
        "operation_template_id": row.operation_template_id,
        "operation_kind": row.operation_kind or row.operation_type or "generic",
        "operation_label_snapshot": row.operation_label or row.process_name,
        "source_block_id": row.source_block_id,
        "block_name_snapshot": row.process_name,
        "library_name_snapshot": row.library_name,
        "material_version_id": material_version_id,
        "press_id": row.press_id,
        "press_mode_id": row.press_mode_id,
        "parameter_values": dict(row.parameter_values or {}),
        "control_parameters": dict(row.control_parameters or {}),
        "step_specific_parameters": step_specific_parameters,
        "initial_geometry": _serialize_geometry(row.initial_geometry),
        "final_geometry": _serialize_geometry(row.final_geometry),
        "metrics": metrics,
        "accumulated_time_start_seconds": start_seconds,
        "duration_seconds": row.duration_seconds,
        "accumulated_time_stop_seconds": stop_seconds,
        "simulation_expected_duration_seconds": (
            float(row.simulation_expected_duration_days) * 86400.0
            if row.simulation_expected_duration_days is not None
            else None
        ),
    }


def _coerce_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_volume_mm3_from_input_block(block: Block) -> float | None:
    props = extract_namespace(normalize_document_block_props(block.props), DOCUMENT_PROPERTIES)
    explicit_volume = _coerce_float(props.get("volume_mm3"))
    if explicit_volume is not None and explicit_volume > 0.0:
        return explicit_volume

    attributes = props.get("attributes")
    if isinstance(attributes, dict):
        explicit_volume = _coerce_float(attributes.get("volume_mm3"))
        if explicit_volume is not None and explicit_volume > 0.0:
            return explicit_volume
        density = _coerce_float(attributes.get("density_kg_per_mm3"))
    else:
        density = None

    weight_kg = _coerce_float(props.get("weight"))
    if weight_kg is None or weight_kg <= 0.0:
        return None

    resolved_density = density or DEFAULT_MATERIAL_DENSITY_KG_PER_MM3
    if resolved_density <= 0.0:
        return None
    return weight_kg / resolved_density


def build_process_cards_for_document_version(session: Session, document_version: DocumentVersion) -> tuple[ProcessCard, ...]:
    document = session.get(Document, document_version.document_id) if document_version.document_id is not None else None
    if document is None:
        return ()

    project = session.get(Project, document.project_id)
    material_version = (
        session.get(MaterialVersion, document.material_version_id)
        if document.material_version_id is not None
        else None
    )
    material_id = material_version.material_id if material_version is not None else (project.material_id if project else None)
    current_material_id = material_id
    cards: list[ProcessCard] = []
    operation_id = 1

    for block in get_ordered_blocks(session, document.document_id):
        if block.block_type_id == "document":
            props = extract_namespace(normalize_document_block_props(block.props), DOCUMENT_PROPERTIES)
            block_material_id = _coerce_int(props.get("material_id"))
            if block_material_id is not None:
                current_material_id = block_material_id

            geometry_type_id = _coerce_int(props.get("geometry_type_id"))
            if geometry_type_id is not None:
                attributes = dict(props.get("attributes") or {})
                mesh_elements = _coerce_int(props.get("mesh_elements"))
                if mesh_elements is not None:
                    attributes["mesh_elements"] = mesh_elements
                volume_mm3 = _infer_volume_mm3_from_input_block(block)
                weight_kg = _coerce_float(props.get("weight"))
                cards.append(
                    ProcessCard(
                        operation_id=operation_id,
                        type_id=geometry_type_id,
                        parameters=attributes,
                        operation_template_id=f"document.geometry.{geometry_type_id}",
                        operation_kind="geometry",
                        operation_label="Billet geometry",
                        source_block_id=block.block_id,
                        material_id=current_material_id,
                        weight_kg=weight_kg,
                        volume_mm3=volume_mm3,
                    )
                )
                operation_id += 1
            continue

    operation_rows = session.scalars(
        select(DocumentOperation)
        .where(DocumentOperation.document_id == document.document_id)
        .order_by(DocumentOperation.operation_order.asc())
    ).all()
    if not operation_rows:
        regenerate_document_operations(session, document.document_id)
        operation_rows = session.scalars(
            select(DocumentOperation)
            .where(DocumentOperation.document_id == document.document_id)
            .order_by(DocumentOperation.operation_order.asc())
        ).all()

    if operation_rows:
        for row in operation_rows:
            operation_template_id = row.operation_template_id
            if not operation_template_id or row.parse_status != "valid":
                continue
            parameters = dict(row.effective_properties or {})
            if row.source_block_type_id == OPERATION_BLOCK_TYPE_ID:
                operation_parameters = extract_namespace(
                    {OPERATION_PROPERTIES: row.operation_properties},
                    OPERATION_PROPERTIES,
                )
                parameters = {
                    **parameters,
                    **operation_target_to_parameters(operation_parameters),
                }
            block_material_id = _coerce_int(parameters.get("material_id"))
            if block_material_id is not None:
                current_material_id = block_material_id
            cards.append(
                ProcessCard(
                    operation_id=operation_id,
                    parameters=parameters,
                    document_operation_id=row.document_operation_id,
                    operation_template_id=operation_template_id,
                    operation_kind=row.operation_kind,
                    operation_label=row.label_snapshot,
                    source_block_id=row.source_block_id,
                    press_id=_coerce_int(parameters.get("press_id")),
                    press_mode_id=_coerce_int(parameters.get("press_mode_id")),
                    die_assembly_id=_coerce_int(parameters.get("die_assembly_id")),
                    top_die_id=_coerce_int(parameters.get("top_die_id")),
                    bottom_die_id=_coerce_int(parameters.get("bottom_die_id")),
                    material_id=current_material_id,
                    weight_kg=_coerce_float(parameters.get("weight")),
                    volume_mm3=_coerce_float(parameters.get("volume_mm3")),
                )
            )
            operation_id += 1
        return tuple(cards)

    return tuple(cards)


def _rebuild_simulation_steps(
    session: Session,
    *,
    document_version: DocumentVersion,
    compiled_program: CompiledControlProgram,
) -> int:
    existing_steps = session.scalars(
        select(SimulationStep).where(SimulationStep.document_version_id == document_version.document_version_id)
    ).all()
    for step in existing_steps:
        session.delete(step)
    session.flush()

    simulation_rows = [row for row in compiled_program.rows if row.is_simulation]
    created_count = 0
    for execution_order, row in enumerate(simulation_rows, start=1):
        payload = _compiled_row_to_step_payload(
            row,
            material_version_id=document_version.document.material_version_id if document_version.document else None,
        )
        step = SimulationStep(
            document_version_id=document_version.document_version_id,
            execution_order=execution_order,
            source_block_id=payload["source_block_id"],
            document_operation_id=payload["document_operation_id"],
            operation_template_id=payload["operation_template_id"],
            operation_kind=str(payload["operation_kind"]),
            operation_label_snapshot=payload["operation_label_snapshot"],
            block_name_snapshot=str(payload["block_name_snapshot"]),
            library_name_snapshot=str(payload["library_name_snapshot"]),
            material_version_id=payload["material_version_id"],
            press_id=row.press_id,
            press_mode_id=row.press_mode_id,
            die_assembly_id=_coerce_int(row.control_parameters.get("die_assembly_id")),
            top_die_id=_coerce_int(row.control_parameters.get("top_die_id")),
            bottom_die_id=_coerce_int(row.control_parameters.get("bottom_die_id")),
            left_die_id=_coerce_int(row.control_parameters.get("left_die_id")),
            right_die_id=_coerce_int(row.control_parameters.get("right_die_id")),
            parameter_values=payload["parameter_values"],
            control_parameters=payload["control_parameters"],
            step_specific_parameters=payload["step_specific_parameters"],
            initial_geometry=payload["initial_geometry"],
            final_geometry=payload["final_geometry"],
            metrics=payload["metrics"],
            accumulated_time_start_seconds=payload["accumulated_time_start_seconds"],
            duration_seconds=payload["duration_seconds"],
            accumulated_time_stop_seconds=payload["accumulated_time_stop_seconds"],
        )
        session.add(step)
        session.flush()

        session.add(
            SimulationStepStatus(
                simulation_step_id=step.simulation_step_id,
                status=SimulationStepStatusEnum.blocked,
                simulation_expected_duration_seconds=payload["simulation_expected_duration_seconds"],
            )
        )
        created_count += 1

    return created_count


def _queue_runnable_step_status(step_status: SimulationStepStatus) -> None:
    if step_status.status is SimulationStepStatusEnum.failed:
        step_status.retry_count += 1
        step_status.attempt_no += 1
    step_status.status = SimulationStepStatusEnum.queued
    step_status.cancel_requested = False
    step_status.simulation_percent = 0
    step_status.queued_at = now_utc()
    step_status.started_at = None
    step_status.heartbeat_at = None
    step_status.finished_at = None
    step_status.simulation_server_id = None
    step_status.worker_name = None
    step_status.last_error = None
    step_status.error_payload = None


class SqlAlchemyLeaseManager(LeaseManager):
    """Persist stale-claim recovery against workflow runtime tables."""

    def __init__(self, *, lease_policy: LeasePolicy | None = None) -> None:
        self._lease_policy = lease_policy or LeasePolicy()

    def heartbeat(self, heartbeat: LeaseHeartbeat) -> None:
        LOGGER.debug("Heartbeat is currently best-effort only job_id=%s", heartbeat.job_id)

    def recover_stale_claims(self) -> int:
        cutoff = now_utc() - timedelta(seconds=self._lease_policy.timeout_seconds)
        recovered = 0
        with session_scope() as session:
            stale_versions = session.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.preprocess_status == PreprocessStatus.running,
                    DocumentVersion.preprocess_started_at.is_not(None),
                    DocumentVersion.preprocess_started_at < cutoff,
                )
            ).all()
            for version in stale_versions:
                version.preprocess_status = PreprocessStatus.queued
                version.preprocess_worker_name = None
                version.preprocess_started_at = None
                version.preprocess_error = "Recovered stale preprocessing claim."
                recovered += 1

            stale_steps = session.scalars(
                select(SimulationStepStatus).where(
                    SimulationStepStatus.status == SimulationStepStatusEnum.running,
                    func.coalesce(SimulationStepStatus.heartbeat_at, SimulationStepStatus.started_at) < cutoff,
                )
            ).all()
            for step_status in stale_steps:
                step_status.status = SimulationStepStatusEnum.queued
                step_status.attempt_no += 1
                step_status.retry_count += 1
                step_status.simulation_server_id = None
                step_status.worker_name = None
                step_status.started_at = None
                step_status.heartbeat_at = None
                step_status.last_error = "Recovered stale solver claim."
                recovered += 1

            stale_posts = session.scalars(
                select(PostprocessingTask).where(
                    PostprocessingTask.status == PostprocessingTaskStatusEnum.running,
                    func.coalesce(PostprocessingTask.heartbeat_at, PostprocessingTask.started_at) < cutoff,
                )
            ).all()
            for task in stale_posts:
                task.status = PostprocessingTaskStatusEnum.queued
                task.retry_count += 1
                task.postprocessing_server_id = None
                task.worker_name = None
                task.started_at = None
                task.heartbeat_at = None
                task.last_error = "Recovered stale postprocessing claim."
                recovered += 1

        if recovered:
            broadcast_notify((PRE_JOBS_CHANNEL, SOLVER_JOBS_CHANNEL, POST_JOBS_CHANNEL, WORKFLOW_EVENTS_CHANNEL), "wake")
        return recovered


@dataclass(slots=True)
class PreJobClaimer(StageJobClaimer):
    def claim_next_job(self, *, worker_name: str) -> ClaimedStageJob | None:
        with session_scope() as session:
            stmt = (
                select(DocumentVersion)
                .where(
                    DocumentVersion.run_switch_status.is_(True),
                    DocumentVersion.preprocess_status.in_([PreprocessStatus.queued, PreprocessStatus.failed]),
                )
                .order_by(
                    case((DocumentVersion.is_editable.is_(False), 0), else_=1),
                    DocumentVersion.simulation_priority.asc().nullslast(),
                    DocumentVersion.last_modified.asc(),
                )
                .with_for_update(skip_locked=True)
            )
            version = session.scalars(stmt).first()
            if version is None:
                return None

            version.preprocess_status = PreprocessStatus.running
            version.preprocess_worker_name = worker_name
            version.preprocess_started_at = now_utc()
            version.preprocess_finished_at = None
            version.preprocess_error = None

            return ClaimedStageJob(
                job_id=version.document_version_id,
                run_id=version.document_version_id,
                stage=WorkflowStage.PRE,
                worker_name=worker_name,
                priority=version.simulation_priority or 0,
            )


@dataclass(slots=True)
class PreJobExecutor(StageJobExecutor):
    compiler: PreprocessorCompiler = PreprocessorCompiler()

    def execute(self, job: ClaimedStageJob) -> None:
        try:
            with session_scope() as session:
                version = session.get(DocumentVersion, int(job.job_id))
                if version is None or version.document_id is None:
                    return

                cards = build_process_cards_for_document_version(session, version)
                compiled_program = self.compiler.compile_from_database(session=session, cards=cards)
                created_steps = _rebuild_simulation_steps(
                    session,
                    document_version=version,
                    compiled_program=compiled_program,
                )
                version.operations_count = len(cards)
                expected_seconds = sum(
                    (
                        step_status.simulation_expected_duration_seconds or 0.0
                        for step_status in session.scalars(
                            select(SimulationStepStatus)
                            .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                            .where(SimulationStep.document_version_id == version.document_version_id)
                        ).all()
                    ),
                    0.0,
                )
                version.simulation_expected_duration_days = expected_seconds / 86400.0 if expected_seconds else 0.0
                version.preprocess_status = PreprocessStatus.ready
                version.preprocess_finished_at = now_utc()
                version.preprocess_error = None
                version.run_switch_status = False
                version.simulation_percent = 0
                version.simulation_server_id = None
                version.last_modified = now_utc()
                LOGGER.info(
                    "Preprocessing completed document_version_id=%s cards=%s simulation_steps=%s",
                    version.document_version_id,
                    len(cards),
                    created_steps,
                )
        except PreprocessorCompileError as exc:
            with session_scope() as session:
                version = session.get(DocumentVersion, int(job.job_id))
                if version is not None:
                    version.preprocess_status = PreprocessStatus.failed
                    version.preprocess_finished_at = now_utc()
                    version.preprocess_error = str(exc)
                    version.simulation_status = SimulationStatus.error if not version.is_editable else SimulationStatus.stop
                    version.run_switch_is_active = False if not version.is_editable else version.run_switch_is_active
            LOGGER.exception("Preprocessing failed document_version_id=%s", job.job_id)
        finally:
            broadcast_notify((WORKFLOW_EVENTS_CHANNEL, SOLVER_JOBS_CHANNEL, POST_JOBS_CHANNEL), "wake")


@dataclass(slots=True)
class SolverJobClaimer(StageJobClaimer):
    def claim_next_job(self, *, worker_name: str) -> ClaimedStageJob | None:
        with session_scope() as session:
            stmt = (
                select(SimulationStepStatus)
                .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                .join(DocumentVersion, DocumentVersion.document_version_id == SimulationStep.document_version_id)
                .where(
                    SimulationStepStatus.status == SimulationStepStatusEnum.queued,
                    SimulationStepStatus.cancel_requested.is_(False),
                    DocumentVersion.run_switch_is_active.is_(True),
                    DocumentVersion.is_editable.is_(False),
                    DocumentVersion.simulation_status != SimulationStatus.pause,
                )
                .order_by(
                    DocumentVersion.simulation_priority.asc().nullslast(),
                    SimulationStepStatus.queued_at.asc().nullslast(),
                    SimulationStep.execution_order.asc(),
                )
                .with_for_update(skip_locked=True)
            )
            step_status = session.scalars(stmt).first()
            if step_status is None:
                return None

            step_status.status = SimulationStepStatusEnum.running
            step_status.worker_name = worker_name
            step_status.started_at = now_utc()
            step_status.heartbeat_at = step_status.started_at
            step_status.simulation_server_id = _resolve_server_id(
                session,
                worker_name=worker_name,
                server_type=ServerType.simulation,
            )

            return ClaimedStageJob(
                job_id=step_status.simulation_step_id,
                run_id=step_status.simulation_step.simulation_step_id,
                stage=WorkflowStage.SOLVER,
                worker_name=worker_name,
                priority=step_status.simulation_step.document_version.simulation_priority or 0,
                payload={"document_version_id": step_status.simulation_step.document_version_id},
            )


@dataclass(slots=True)
class SolverJobExecutor(StageJobExecutor):
    def execute(self, job: ClaimedStageJob) -> None:
        with session_scope() as session:
            step_status = session.get(SimulationStepStatus, int(job.job_id))
            if step_status is None:
                return
            step_status.simulation_percent = 100
            step_status.heartbeat_at = now_utc()
            step_status.finished_at = now_utc()
            step_status.status = SimulationStepStatusEnum.finished
            step_status.runtime_artifacts = {
                **dict(step_status.runtime_artifacts or {}),
                "execution_result": "placeholder-success",
                "finished_by": job.worker_name,
                "finished_at": step_status.finished_at.isoformat(),
            }
            step_status.last_error = None
            step_status.error_payload = None

            version = step_status.simulation_step.document_version
            version.simulation_server_id = step_status.simulation_server_id
            version.last_modified = now_utc()

        broadcast_notify((WORKFLOW_EVENTS_CHANNEL, POST_JOBS_CHANNEL, SOLVER_JOBS_CHANNEL), "wake")


@dataclass(slots=True)
class PostJobClaimer(StageJobClaimer):
    def claim_next_job(self, *, worker_name: str) -> ClaimedStageJob | None:
        with session_scope() as session:
            stmt = (
                select(PostprocessingTask)
                .join(SimulationStep, SimulationStep.simulation_step_id == PostprocessingTask.simulation_step_id)
                .join(DocumentVersion, DocumentVersion.document_version_id == SimulationStep.document_version_id)
                .where(
                    PostprocessingTask.status == PostprocessingTaskStatusEnum.queued,
                    DocumentVersion.run_switch_is_active.is_(True),
                )
                .order_by(
                    DocumentVersion.simulation_priority.asc().nullslast(),
                    PostprocessingTask.queued_at.asc().nullslast(),
                    SimulationStep.execution_order.asc(),
                )
                .with_for_update(skip_locked=True)
            )
            task = session.scalars(stmt).first()
            if task is None:
                return None

            task.status = PostprocessingTaskStatusEnum.running
            task.worker_name = worker_name
            task.started_at = now_utc()
            task.heartbeat_at = task.started_at
            task.postprocessing_server_id = _resolve_server_id(
                session,
                worker_name=worker_name,
                server_type=ServerType.post,
            )

            return ClaimedStageJob(
                job_id=task.postprocessing_task_id,
                run_id=task.simulation_step.document_version_id,
                stage=WorkflowStage.POST,
                worker_name=worker_name,
                priority=task.simulation_step.document_version.simulation_priority or 0,
                payload={"simulation_step_id": task.simulation_step_id},
            )


@dataclass(slots=True)
class PostJobExecutor(StageJobExecutor):
    def execute(self, job: ClaimedStageJob) -> None:
        with session_scope() as session:
            task = session.get(PostprocessingTask, int(job.job_id))
            if task is None:
                return

            task.heartbeat_at = now_utc()
            task.finished_at = now_utc()
            task.status = PostprocessingTaskStatusEnum.finished
            task.output_payload = {
                **dict(task.output_payload or {}),
                "result": "placeholder-success",
                "finished_by": job.worker_name,
                "finished_at": task.finished_at.isoformat(),
            }
            task.last_error = None
            task.error_payload = None

        broadcast_notify((WORKFLOW_EVENTS_CHANNEL,), "wake")


class DatabaseCoordinatorHooks:
    """Coordinator hooks backed by the new runtime tables."""

    def recover_stale_claims(self) -> int:
        return 0

    def reconcile_pre_jobs(self) -> int:
        changed = 0
        with session_scope() as session:
            versions = session.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.run_switch_status.is_(True),
                    DocumentVersion.preprocess_status.not_in([PreprocessStatus.running, PreprocessStatus.queued]),
                )
            ).all()
            for version in versions:
                version.preprocess_status = PreprocessStatus.queued
                version.preprocess_error = None
                changed += 1

        if changed:
            broadcast_notify((PRE_JOBS_CHANNEL,), "wake")
        return changed

    def advance_solver_pipeline(self) -> int:
        changed = 0
        with session_scope() as session:
            versions = session.scalars(
                select(DocumentVersion)
                .where(
                    DocumentVersion.is_editable.is_(False),
                    DocumentVersion.run_switch_is_active.is_(True),
                    DocumentVersion.run_switch_status.is_(False),
                    DocumentVersion.preprocess_status == PreprocessStatus.ready,
                )
                .order_by(DocumentVersion.simulation_priority.asc().nullslast(), DocumentVersion.document_version_id.asc())
            ).all()

            for version in versions:
                if version.simulation_status is SimulationStatus.pause:
                    continue

                active_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status.in_([SimulationStepStatusEnum.queued, SimulationStepStatusEnum.running]),
                    )
                ).scalar() or 0
                if active_step_count:
                    continue

                next_step_status = session.scalars(
                    select(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status.in_([SimulationStepStatusEnum.blocked, SimulationStepStatusEnum.failed]),
                    )
                    .order_by(SimulationStep.execution_order.asc())
                    .with_for_update(skip_locked=True)
                ).first()
                if next_step_status is None:
                    continue

                _queue_runnable_step_status(next_step_status)
                changed += 1

        if changed:
            broadcast_notify((SOLVER_JOBS_CHANNEL,), "wake")
        return changed

    def enqueue_post_jobs(self) -> int:
        changed = 0
        with session_scope() as session:
            finished_steps = session.scalars(
                select(SimulationStep)
                .join(SimulationStepStatus, SimulationStepStatus.simulation_step_id == SimulationStep.simulation_step_id)
                .join(DocumentVersion, DocumentVersion.document_version_id == SimulationStep.document_version_id)
                .where(
                    SimulationStepStatus.status == SimulationStepStatusEnum.finished,
                    DocumentVersion.run_switch_is_active.is_(True),
                )
            ).all()

            for step in finished_steps:
                existing = session.execute(
                    select(func.count())
                    .select_from(PostprocessingTask)
                    .where(
                        PostprocessingTask.simulation_step_id == step.simulation_step_id,
                        PostprocessingTask.task_kind == "full",
                    )
                ).scalar() or 0
                if existing:
                    continue
                session.add(
                    PostprocessingTask(
                        simulation_step_id=step.simulation_step_id,
                        task_kind="full",
                        status=PostprocessingTaskStatusEnum.queued,
                        queued_at=now_utc(),
                    )
                )
                changed += 1

        if changed:
            broadcast_notify((POST_JOBS_CHANNEL,), "wake")
        return changed

    def sync_workflow_statuses(self) -> int:
        changed = 0
        queue_candidates: list[DocumentVersion] = []
        with session_scope() as session:
            versions = session.scalars(
                select(DocumentVersion).where(DocumentVersion.document_id.is_not(None))
            ).all()
            current_time = now_utc()

            for version in versions:
                total_steps = session.execute(
                    select(func.count())
                    .select_from(SimulationStep)
                    .where(SimulationStep.document_version_id == version.document_version_id)
                ).scalar() or 0
                finished_steps = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.finished,
                    )
                ).scalar() or 0
                running_steps = session.scalars(
                    select(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.running,
                    )
                ).all()
                queued_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.queued,
                    )
                ).scalar() or 0
                blocked_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.blocked,
                    )
                ).scalar() or 0
                failed_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.failed,
                    )
                ).scalar() or 0

                posts = session.scalars(
                    select(PostprocessingTask)
                    .join(SimulationStep, SimulationStep.simulation_step_id == PostprocessingTask.simulation_step_id)
                    .where(SimulationStep.document_version_id == version.document_version_id)
                ).all()
                running_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.running)
                queued_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.queued)
                failed_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.failed)
                finished_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.finished)

                expected_seconds = session.execute(
                    select(func.coalesce(func.sum(SimulationStepStatus.simulation_expected_duration_seconds), 0.0))
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                    .where(SimulationStep.document_version_id == version.document_version_id)
                ).scalar() or 0.0
                new_expected_days = float(expected_seconds) / 86400.0 if expected_seconds else 0.0
                if (version.simulation_expected_duration_days or 0.0) != new_expected_days:
                    version.simulation_expected_duration_days = new_expected_days
                    changed += 1

                new_percent = int(round((finished_steps / total_steps) * 100.0)) if total_steps else 0
                if (version.simulation_percent or 0) != new_percent:
                    version.simulation_percent = new_percent
                    changed += 1

                new_server_id = running_steps[0].simulation_server_id if running_steps else None
                if version.simulation_server_id != new_server_id:
                    version.simulation_server_id = new_server_id
                    changed += 1

                previous_status = version.simulation_status
                if version.is_editable:
                    new_status = SimulationStatus.stop
                elif failed_step_count or failed_post_count or version.preprocess_status is PreprocessStatus.failed:
                    new_status = SimulationStatus.error
                    version.run_switch_is_active = False
                elif running_steps or running_post_count:
                    new_status = SimulationStatus.run
                    if version.ran_at is None:
                        version.ran_at = current_time
                elif version.simulation_status is SimulationStatus.pause and version.run_switch_is_active:
                    new_status = SimulationStatus.pause
                elif version.run_switch_status or version.preprocess_status in {PreprocessStatus.queued, PreprocessStatus.running}:
                    new_status = SimulationStatus.stop
                elif (
                    total_steps > 0
                    and finished_steps == total_steps
                    and len(posts) >= total_steps
                    and finished_post_count == len(posts)
                    and queued_post_count == 0
                ):
                    new_status = SimulationStatus.done
                    version.run_switch_is_active = False
                    version.finished_at = version.finished_at or current_time
                else:
                    new_status = SimulationStatus.stop

                if previous_status != new_status:
                    version.simulation_status = new_status
                    changed += 1

                if (
                    not version.is_editable
                    and (
                        version.run_switch_is_active
                        or version.simulation_status in {SimulationStatus.run, SimulationStatus.pause}
                    )
                    and version.simulation_status is not SimulationStatus.done
                ):
                    queue_candidates.append(version)

                if not version.run_switch_is_active and version.simulation_status not in {SimulationStatus.run, SimulationStatus.done}:
                    queued_steps = session.scalars(
                        select(SimulationStepStatus)
                        .join(SimulationStep, SimulationStep.simulation_step_id == SimulationStepStatus.simulation_step_id)
                        .where(
                            SimulationStep.document_version_id == version.document_version_id,
                            SimulationStepStatus.status.in_([SimulationStepStatusEnum.queued, SimulationStepStatusEnum.blocked]),
                        )
                    ).all()
                    for step_status in queued_steps:
                        if step_status.status is not SimulationStepStatusEnum.cancelled:
                            step_status.status = SimulationStepStatusEnum.cancelled
                            changed += 1

                if queued_step_count or blocked_step_count or running_steps or queued_post_count or running_post_count:
                    version.finished_at = None

            queue_candidates.sort(
                key=lambda item: (
                    0 if item.simulation_status is SimulationStatus.run else 1,
                    item.simulation_priority if item.simulation_priority is not None else 32767,
                    item.document_version_id,
                )
            )
            for index, version in enumerate(queue_candidates, start=1):
                if version.simulation_queue_number != index:
                    version.simulation_queue_number = index
                    changed += 1
                if version.simulation_queue_row_number != index:
                    version.simulation_queue_row_number = index
                    changed += 1

            active_ids = {version.document_version_id for version in queue_candidates}
            inactive_versions = [version for version in versions if version.document_version_id not in active_ids]
            for version in inactive_versions:
                if version.simulation_queue_number is not None:
                    version.simulation_queue_number = None
                    changed += 1
                if version.simulation_queue_row_number is not None:
                    version.simulation_queue_row_number = None
                    changed += 1

        return changed

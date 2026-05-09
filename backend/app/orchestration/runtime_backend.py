"""DB-backed coordinator and worker runtime adapters."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import socket
from typing import Iterable, Sequence

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
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
from app.services.block_props import as_dict
from app.services.document_operations import regenerate_document_operations
from app.services.preprocessor.compiler import (
    CompiledControlProgram,
    CompiledControlProgramRow,
    PreprocessorCompiler,
    PreprocessorCompileError,
    ProcessCard,
)
from app.services.preprocessor.surface_artifacts import write_surface_artifacts_for_compiled_meshes
from app.services.preprocessor.geometry import GeneratedGeometry
from app.services.preprocessor.operation_keys import DOCUMENT_INITIAL_DATA_TEMPLATE_ID, RADIAL_ROTATION_HEIGHT_FEED


LOGGER = logging.getLogger(__name__)

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
        # Explicitly expose orientation metadata slots. The current migrated Pre
        # math does not emit normalized basis/top-marker data yet, so callers
        # must treat missing values as unavailable instead of guessing.
        "basis": None,
        "top_marker": None,
        "orientation_metadata_status": "missing",
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


def _flatten_mapping_to_dotted_parameters(
    value: object,
    *,
    prefix: str = "",
) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    flattened: dict[str, object] = {}
    for key, item in value.items():
        dotted_key = f"{prefix}.{key}" if prefix else str(key)
        flattened[dotted_key] = item
        if isinstance(item, dict):
            flattened.update(_flatten_mapping_to_dotted_parameters(item, prefix=dotted_key))
    return flattened


def _document_initial_parameters_from_target(target: object) -> dict[str, object]:
    target_mapping = as_dict(target)
    if not target_mapping:
        return {}

    input_stock = as_dict(target_mapping.get("input_stock"))
    material = as_dict(target_mapping.get("material"))
    mesh = as_dict(target_mapping.get("mesh"))
    process_data = as_dict(target_mapping.get("process_data"))
    document_info = as_dict(target_mapping.get("document_info"))
    attributes = as_dict(input_stock.get("attributes"))

    parameters: dict[str, object] = _flatten_mapping_to_dotted_parameters(target_mapping)
    parameters.update(attributes)
    parameters.update(
        {
            "geometry_type_id": input_stock.get("geometry_type_id"),
            "weight": input_stock.get("weight_kg"),
            "weight_kg": input_stock.get("weight_kg"),
            "volume_mm3": input_stock.get("volume_mm3"),
            "mesh_elements": mesh.get("mesh_elements"),
            "material_id": material.get("material_id"),
            "material_name": material.get("material_name"),
            "material_version_id": material.get("material_version_id"),
            "heat_no": process_data.get("heat_no"),
            "finished_size": process_data.get("finished_size"),
            "remarks": process_data.get("remarks"),
            "document_name": document_info.get("name"),
        }
    )
    return parameters


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

    operation_rows = session.scalars(
        select(DocumentOperation)
        .where(DocumentOperation.document_id == document.document_id)
        .order_by(DocumentOperation.operation_order.asc())
    ).all()
    if not operation_rows or not any(
        row.operation_template_id == DOCUMENT_INITIAL_DATA_TEMPLATE_ID
        for row in operation_rows
    ):
        regenerate_document_operations(session, document.document_id)
        operation_rows = session.scalars(
            select(DocumentOperation)
            .where(DocumentOperation.document_id == document.document_id)
            .order_by(DocumentOperation.operation_order.asc())
        ).all()

    if operation_rows:
        for row in operation_rows:
            operation_template_id = row.operation_template_id
            if row.parse_status != "valid":
                error_summary = "; ".join(
                    str(item.get("message") or item)
                    for item in (row.parse_errors or [])
                    if isinstance(item, dict)
                ) or str(row.parse_errors or "unknown parse error")
                raise PreprocessorCompileError(
                    f"Document operation #{row.operation_order} from block {row.source_block_id} is invalid: "
                    f"{error_summary}",
                    operation_id=row.operation_order,
                    document_operation_id=row.document_operation_id,
                    operation_template_id=row.operation_template_id,
                    source_block_id=row.source_block_id,
                )
            if not operation_template_id:
                continue
            parameters = dict(row.operation_parameters or {})
            if operation_template_id == DOCUMENT_INITIAL_DATA_TEMPLATE_ID:
                parameters = _document_initial_parameters_from_target(parameters)
                block_material_id = _coerce_int(parameters.get("material_id"))
                if block_material_id is not None:
                    current_material_id = block_material_id
                cards.append(
                    ProcessCard(
                        operation_id=operation_id,
                        type_id=_coerce_int(parameters.get("geometry_type_id")),
                        parameters=parameters,
                        document_operation_id=row.document_operation_id,
                        operation_template_id=operation_template_id,
                        operation_kind=row.operation_kind,
                        operation_label=row.label_snapshot,
                        source_block_id=row.source_block_id,
                        material_id=current_material_id,
                        weight_kg=_coerce_float(parameters.get("weight_kg")),
                        volume_mm3=_coerce_float(parameters.get("volume_mm3")),
                    )
                )
                operation_id += 1
                continue
            if (
                operation_template_id == RADIAL_ROTATION_HEIGHT_FEED
                and "radial_feed" not in parameters
                and parameters.get("feed_first") not in (None, "")
            ):
                parameters["radial_feed"] = parameters["feed_first"]
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


def _valid_document_operations_for_version(
    session: Session,
    *,
    document_version: DocumentVersion,
) -> list[DocumentOperation]:
    document_id = document_version.document_id
    if document_id is None:
        raise PreprocessorCompileError(
            f"Document version {document_version.document_version_id} has no document_id."
        )
    return list(session.scalars(
        select(DocumentOperation)
        .where(
            DocumentOperation.document_id == document_id,
            DocumentOperation.parse_status == "valid",
            DocumentOperation.operation_template_id.is_not(None),
            DocumentOperation.operation_template_id != "",
        )
        .order_by(DocumentOperation.operation_order.asc())
    ).all())


def _step_snapshot_label(operation_row: DocumentOperation) -> str:
    return (
        operation_row.label_snapshot
        or operation_row.operation_template_id
        or operation_row.operation_kind
        or operation_row.source_block_type_id
        or "operation"
    )


def _prepare_simulation_steps_for_pre_run(
    session: Session,
    *,
    document_version: DocumentVersion,
    valid_document_operations: Sequence[DocumentOperation],
) -> set[int]:
    """Reset sibling rows before Pre starts so stale output is not mistaken for current output."""

    document = document_version.document
    valid_ids: set[int] = set()
    for execution_order, operation_row in enumerate(valid_document_operations, start=1):
        document_operation_id = int(operation_row.document_operation_id)
        valid_ids.add(document_operation_id)
        snapshot_label = _step_snapshot_label(operation_row)
        step = session.get(SimulationStep, document_operation_id)
        if step is None:
            step = SimulationStep(document_operation_id=document_operation_id)
            session.add(step)

        step.document_version_id = document_version.document_version_id
        step.execution_order = execution_order
        step.source_block_id = operation_row.source_block_id
        step.operation_template_id = operation_row.operation_template_id
        step.operation_kind = operation_row.operation_kind or "generic"
        step.operation_label_snapshot = operation_row.label_snapshot
        step.preprocess_ready = False
        step.block_name_snapshot = snapshot_label
        step.library_name_snapshot = snapshot_label
        step.material_version_id = document.material_version_id if document is not None else None
        step.press_id = None
        step.press_mode_id = None
        step.die_assembly_id = None
        step.top_die_id = None
        step.bottom_die_id = None
        step.left_die_id = None
        step.right_die_id = None
        step.parameter_values = {}
        step.control_parameters = {}
        step.step_specific_parameters = {}
        step.initial_geometry = None
        step.final_geometry = None
        step.metrics = {
            "preprocessor_status": "pending",
            "document_operation_id": document_operation_id,
            "operation_template_id": operation_row.operation_template_id,
            "preprocessor_started_at": now_utc().isoformat(),
        }
        step.accumulated_time_start_seconds = None
        step.duration_seconds = None
        step.accumulated_time_stop_seconds = None

        step_status = session.get(SimulationStepStatus, document_operation_id)
        if step_status is None:
            step_status = SimulationStepStatus(document_operation_id=document_operation_id)
            session.add(step_status)
        step_status.status = SimulationStepStatusEnum.blocked
        step_status.cancel_requested = False
        step_status.simulation_percent = 0
        step_status.simulation_expected_duration_seconds = None
        step_status.simulation_server_id = None
        step_status.worker_name = None
        step_status.queued_at = None
        step_status.started_at = None
        step_status.heartbeat_at = None
        step_status.finished_at = None
        step_status.runtime_artifacts = {}
        step_status.last_error = None
        step_status.error_payload = None
    return valid_ids


def _write_compiled_simulation_step(
    session: Session,
    *,
    document_version: DocumentVersion,
    row: CompiledControlProgramRow,
    execution_order: int,
    valid_document_operation_ids: set[int],
    seen_document_operation_ids: set[int],
) -> None:
    payload = _compiled_row_to_step_payload(
        row,
        material_version_id=document_version.document.material_version_id if document_version.document else None,
    )
    document_operation_id = _coerce_int(payload["document_operation_id"])
    if document_operation_id is None:
        raise PreprocessorCompileError(
            f"Compiled simulation row #{execution_order} has no source document_operation_id."
        )
    if document_operation_id not in valid_document_operation_ids:
        raise PreprocessorCompileError(
            f"Compiled simulation row #{execution_order} references document_operation_id={document_operation_id}, "
            f"which does not belong to document_id={document_version.document_id}."
        )
    if document_operation_id in seen_document_operation_ids:
        raise PreprocessorCompileError(
            f"Compiled simulation row #{execution_order} duplicates document_operation_id={document_operation_id}."
        )
    seen_document_operation_ids.add(document_operation_id)

    step = session.get(SimulationStep, document_operation_id)
    if step is None:
        step = SimulationStep(document_operation_id=document_operation_id)
        session.add(step)

    metrics = dict(payload["metrics"])
    metrics.update(
        {
            "preprocessor_status": "compiled",
            "document_operation_id": document_operation_id,
            "preprocessor_compiled_at": now_utc().isoformat(),
        }
    )

    step.document_version_id = document_version.document_version_id
    step.execution_order = execution_order
    step.source_block_id = payload["source_block_id"]
    step.operation_template_id = payload["operation_template_id"]
    step.operation_kind = str(payload["operation_kind"])
    step.operation_label_snapshot = payload["operation_label_snapshot"]
    step.preprocess_ready = True
    step.block_name_snapshot = str(payload["block_name_snapshot"])
    step.library_name_snapshot = str(payload["library_name_snapshot"])
    step.material_version_id = payload["material_version_id"]
    step.press_id = row.press_id
    step.press_mode_id = row.press_mode_id
    step.die_assembly_id = _coerce_int(row.control_parameters.get("die_assembly_id"))
    step.top_die_id = _coerce_int(row.control_parameters.get("top_die_id"))
    step.bottom_die_id = _coerce_int(row.control_parameters.get("bottom_die_id"))
    step.left_die_id = _coerce_int(row.control_parameters.get("left_die_id"))
    step.right_die_id = _coerce_int(row.control_parameters.get("right_die_id"))
    step.parameter_values = payload["parameter_values"]
    step.control_parameters = payload["control_parameters"]
    step.step_specific_parameters = payload["step_specific_parameters"]
    step.initial_geometry = payload["initial_geometry"]
    step.final_geometry = payload["final_geometry"]
    compiled_meshes = {
        kind: mesh
        for kind, mesh in (
            ("initial", row.initial_surface_mesh),
            ("final", row.final_surface_mesh),
        )
        if mesh is not None
    }
    try:
        generated_surface_artifacts = write_surface_artifacts_for_compiled_meshes(
            step,
            document_id=int(document_version.document_id),
            meshes=compiled_meshes,
            force=True,
        )
        if generated_surface_artifacts is not None:
            metrics["surface_artifacts"] = generated_surface_artifacts.summary
    except Exception as exc:
        LOGGER.warning(
            "Failed to write legacy surface artifacts document_version_id=%s document_operation_id=%s: %s",
            document_version.document_version_id,
            document_operation_id,
            exc,
        )
        metrics["legacy_surface_artifact_error"] = str(exc)
    step.metrics = metrics
    step.accumulated_time_start_seconds = payload["accumulated_time_start_seconds"]
    step.duration_seconds = payload["duration_seconds"]
    step.accumulated_time_stop_seconds = payload["accumulated_time_stop_seconds"]

    step_status = session.get(SimulationStepStatus, document_operation_id)
    if step_status is None:
        step_status = SimulationStepStatus(
            document_operation_id=document_operation_id,
        )
        session.add(step_status)
    step_status.status = SimulationStepStatusEnum.blocked
    step_status.cancel_requested = False
    step_status.simulation_percent = 0
    step_status.simulation_expected_duration_seconds = payload["simulation_expected_duration_seconds"]
    step_status.simulation_server_id = None
    step_status.worker_name = None
    step_status.queued_at = None
    step_status.started_at = None
    step_status.heartbeat_at = None
    step_status.finished_at = None
    step_status.runtime_artifacts = {}
    step_status.last_error = None
    step_status.error_payload = None


def _write_compiled_simulation_step_committed(
    *,
    document_version_id: int,
    row: CompiledControlProgramRow,
    execution_order: int,
    valid_document_operation_ids: set[int],
    seen_document_operation_ids: set[int],
) -> None:
    """Persist one compiled Pre row in its own transaction."""

    with session_scope() as write_session:
        document_version = write_session.get(DocumentVersion, document_version_id)
        if document_version is None or document_version.document_id is None:
            raise PreprocessorCompileError(
                f"Document version {document_version_id} disappeared while writing Pre row #{execution_order}."
            )
        _write_compiled_simulation_step(
            write_session,
            document_version=document_version,
            row=row,
            execution_order=execution_order,
            valid_document_operation_ids=valid_document_operation_ids,
            seen_document_operation_ids=seen_document_operation_ids,
        )


def _assert_all_rows_compiled(
    *,
    valid_document_operation_ids: set[int],
    seen_document_operation_ids: set[int],
) -> None:
    missing_compiled_ids = valid_document_operation_ids - seen_document_operation_ids
    if missing_compiled_ids:
        raise PreprocessorCompileError(
            f"Missing compiled simulation rows for document_operation_id values: {sorted(missing_compiled_ids)}"
        )


def _rebuild_simulation_steps(
    session: Session,
    *,
    document_version: DocumentVersion,
    compiled_program: CompiledControlProgram,
) -> int:
    document_id = document_version.document_id
    valid_document_operations = _valid_document_operations_for_version(
        session,
        document_version=document_version,
    )
    valid_document_operation_ids = {
        int(row.document_operation_id)
        for row in valid_document_operations
    }

    compiled_rows = tuple(compiled_program.rows)
    if len(compiled_rows) != len(valid_document_operations):
        raise PreprocessorCompileError(
            f"Compiled row count {len(compiled_rows)} does not match valid document operation count "
            f"{len(valid_document_operations)} for document_id={document_id}."
        )

    valid_document_operation_ids = _prepare_simulation_steps_for_pre_run(
        session,
        document_version=document_version,
        valid_document_operations=valid_document_operations,
    )
    seen_document_operation_ids: set[int] = set()
    updated_count = 0
    for execution_order, row in enumerate(compiled_rows, start=1):
        _write_compiled_simulation_step(
            session,
            document_version=document_version,
            row=row,
            execution_order=execution_order,
            valid_document_operation_ids=valid_document_operation_ids,
            seen_document_operation_ids=seen_document_operation_ids,
        )
        updated_count += 1

    _assert_all_rows_compiled(
        valid_document_operation_ids=valid_document_operation_ids,
        seen_document_operation_ids=seen_document_operation_ids,
    )

    return updated_count


def _compile_and_write_simulation_steps_incrementally(
    session: Session,
    *,
    document_version: DocumentVersion,
    cards: Sequence[ProcessCard],
    compiler: PreprocessorCompiler,
) -> int:
    """Compile and persist Pre output row-by-row.

    Each successful row is committed in its own short transaction before the
    next row starts compiling. If a later row fails, already compiled rows stay
    visible in the Steps view and the failed row receives diagnostics from the
    outer error handler.
    """

    valid_document_operations = _valid_document_operations_for_version(
        session,
        document_version=document_version,
    )
    if len(cards) != len(valid_document_operations):
        raise PreprocessorCompileError(
            f"Process card count {len(cards)} does not match valid document operation count "
            f"{len(valid_document_operations)} for document_id={document_version.document_id}."
        )
    valid_document_operation_ids = _prepare_simulation_steps_for_pre_run(
        session,
        document_version=document_version,
        valid_document_operations=valid_document_operations,
    )
    session.commit()
    broadcast_notify((WORKFLOW_EVENTS_CHANNEL,), "pre_started")

    document_version_id = int(document_version.document_version_id)
    seen_document_operation_ids: set[int] = set()
    updated_count = 0
    for execution_order, row in enumerate(
        compiler.iter_compile_from_database(session=session, cards=cards),
        start=1,
    ):
        _write_compiled_simulation_step_committed(
            document_version_id=document_version_id,
            row=row,
            execution_order=execution_order,
            valid_document_operation_ids=valid_document_operation_ids,
            seen_document_operation_ids=seen_document_operation_ids,
        )
        updated_count += 1
        broadcast_notify(
            (WORKFLOW_EVENTS_CHANNEL,),
            f"pre_row:{document_version_id}:{execution_order}",
        )

    _assert_all_rows_compiled(
        valid_document_operation_ids=valid_document_operation_ids,
        seen_document_operation_ids=seen_document_operation_ids,
    )
    return updated_count


def _record_preprocess_compile_failure(
    session: Session,
    *,
    document_version: DocumentVersion,
    error: PreprocessorCompileError,
) -> None:
    """Store row-level Pre failure diagnostics on the sibling simulation step."""

    if error.document_operation_id is None:
        return

    step = session.get(SimulationStep, int(error.document_operation_id))
    if step is None:
        return

    step.document_version_id = document_version.document_version_id
    step.preprocess_ready = False
    metrics = dict(step.metrics or {})
    metrics.update(
        {
            "preprocessor_status": "failed",
            "preprocessor_error": str(error),
            "preprocessor_failed_at": now_utc().isoformat(),
            "operation_id": error.operation_id,
            "document_operation_id": error.document_operation_id,
            "operation_template_id": error.operation_template_id,
        }
    )
    step.metrics = metrics

    step_status = session.get(SimulationStepStatus, int(error.document_operation_id))
    if step_status is None:
        step_status = SimulationStepStatus(
            document_operation_id=int(error.document_operation_id),
            status=SimulationStepStatusEnum.failed,
        )
        session.add(step_status)
    else:
        step_status.status = SimulationStepStatusEnum.failed
    step_status.cancel_requested = False
    step_status.simulation_percent = 0
    step_status.simulation_server_id = None
    step_status.worker_name = None
    step_status.started_at = None
    step_status.heartbeat_at = None
    step_status.finished_at = now_utc()
    step_status.last_error = f"Preprocessor failed: {error}"
    step_status.error_payload = {
        "stage": "preprocessor",
        "operation_id": error.operation_id,
        "document_operation_id": error.document_operation_id,
        "operation_template_id": error.operation_template_id,
        "source_block_id": str(error.source_block_id) if error.source_block_id is not None else None,
        "message": str(error),
    }


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
                version.operations_count = len(cards)
                updated_steps = _compile_and_write_simulation_steps_incrementally(
                    session,
                    document_version=version,
                    cards=cards,
                    compiler=self.compiler,
                )
                expected_seconds = sum(
                    (
                        step_status.simulation_expected_duration_seconds or 0.0
                        for step_status in session.scalars(
                            select(SimulationStepStatus)
                            .join(
                                SimulationStep,
                                SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id,
                            )
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
                    updated_steps,
                )
        except PreprocessorCompileError as exc:
            with session_scope() as session:
                version = session.get(DocumentVersion, int(job.job_id))
                if version is not None:
                    _record_preprocess_compile_failure(
                        session,
                        document_version=version,
                        error=exc,
                    )
                    version.preprocess_status = PreprocessStatus.failed
                    version.preprocess_finished_at = now_utc()
                    version.preprocess_error = str(exc)
                    # A failed compile requires user/API correction before retry.
                    # Leaving the run switch on makes the worker immediately
                    # reclaim the same invalid document in a tight loop.
                    version.run_switch_status = False
                    version.simulation_status = SimulationStatus.error if not version.is_editable else SimulationStatus.stop
                    version.run_switch_is_active = False if not version.is_editable else version.run_switch_is_active
            LOGGER.error(
                "Preprocessing failed document_version_id=%s: %s",
                job.job_id,
                exc,
                exc_info=LOGGER.isEnabledFor(logging.DEBUG),
            )
        finally:
            broadcast_notify((WORKFLOW_EVENTS_CHANNEL, SOLVER_JOBS_CHANNEL, POST_JOBS_CHANNEL), "wake")


@dataclass(slots=True)
class SolverJobClaimer(StageJobClaimer):
    def claim_next_job(self, *, worker_name: str) -> ClaimedStageJob | None:
        with session_scope() as session:
            stmt = (
                select(SimulationStepStatus)
                .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
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
                job_id=step_status.document_operation_id,
                run_id=step_status.simulation_step.document_operation_id,
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
                .join(SimulationStep, SimulationStep.document_operation_id == PostprocessingTask.document_operation_id)
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
                payload={"document_operation_id": task.document_operation_id},
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
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status.in_([SimulationStepStatusEnum.queued, SimulationStepStatusEnum.running]),
                    )
                ).scalar() or 0
                if active_step_count:
                    continue

                next_step_status = session.scalars(
                    select(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
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
                .join(SimulationStepStatus, SimulationStepStatus.document_operation_id == SimulationStep.document_operation_id)
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
                        PostprocessingTask.document_operation_id == step.document_operation_id,
                        PostprocessingTask.task_kind == "full",
                    )
                ).scalar() or 0
                if existing:
                    continue
                session.add(
                    PostprocessingTask(
                        document_operation_id=step.document_operation_id,
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
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.finished,
                    )
                ).scalar() or 0
                running_steps = session.scalars(
                    select(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.running,
                    )
                ).all()
                queued_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.queued,
                    )
                ).scalar() or 0
                blocked_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.blocked,
                    )
                ).scalar() or 0
                failed_step_count = session.execute(
                    select(func.count())
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
                    .where(
                        SimulationStep.document_version_id == version.document_version_id,
                        SimulationStepStatus.status == SimulationStepStatusEnum.failed,
                    )
                ).scalar() or 0

                posts = session.scalars(
                    select(PostprocessingTask)
                    .join(SimulationStep, SimulationStep.document_operation_id == PostprocessingTask.document_operation_id)
                    .where(SimulationStep.document_version_id == version.document_version_id)
                ).all()
                running_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.running)
                queued_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.queued)
                failed_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.failed)
                finished_post_count = sum(1 for task in posts if task.status == PostprocessingTaskStatusEnum.finished)

                expected_seconds = session.execute(
                    select(func.coalesce(func.sum(SimulationStepStatus.simulation_expected_duration_seconds), 0.0))
                    .select_from(SimulationStepStatus)
                    .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
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
                        .join(SimulationStep, SimulationStep.document_operation_id == SimulationStepStatus.document_operation_id)
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

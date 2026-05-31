from datetime import datetime
import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.document.block import Block
from app.models.document.document import Document, DocumentEditSession, DocumentVersion, PreprocessStatus
from app.models.document.document_operation import DocumentOperation
from app.models.library.material import MaterialVersion
from app.models.project import Project
from app.models.user import User
from app.schemas import (
    BlockDiffEntry,
    DocumentCopyRequest,
    DocumentCreate,
    DocumentDiffResponse,
    DocumentOperationListResponse,
    DocumentOperationResponse,
    DocumentPreprocessQueueResponse,
    DocumentSimulationStepListResponse,
    DocumentSimulationStepResponse,
    DocumentSimulationStepSurfaceResponse,
    DocumentLineageNode,
    DocumentLineageResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    EditSessionListResponse,
    EditSessionResponse,
    EditSessionStartRequest,
    SimulationStepDiagnosticsResponse,
    SimulationStepResponse,
    SimulationStepStatusResponse,
)
from app.services.block_service import create_block, get_ordered_blocks
from app.services.block_type_service import initialize_system_blocks
from app.services.document_operations import regenerate_document_operations
from app.services.preprocessor.operation_keys import DOCUMENT_INITIAL_DATA_TEMPLATE_ID, FURNACE_TEMPLATE_ID
from app.services.preprocessor.surface_artifacts import (
    ensure_surface_artifacts_for_step,
    surface_artifact_abs_path,
    with_surface_artifact_urls,
)
from app.services.preprocessor.surface_mesh import SurfaceMeshError
from app.services.workflow_commands import (
    WorkflowCommandError,
    assert_document_editable,
    create_initial_working_version,
    get_latest_document_version,
    notify_after_edit,
    queue_document_preprocessing,
)
from app.models.workflow_runtime import SimulationStep, SimulationStepStatus

router = APIRouter(prefix="/documents", tags=["documents"])


def check_document_access(db: Session, document_id: int, user_id: int) -> Document:
    document = db.execute(
        select(Document).filter(Document.document_id == document_id)
    ).scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    project = db.execute(
        select(Project).filter(Project.project_id == document.project_id)
    ).scalars().first()
    if not project or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Project not found")

    is_owner = project.user_id == user_id
    is_delegate_editor = document.editor_user_id == user_id
    if not is_owner and not is_delegate_editor:
        raise HTTPException(status_code=403, detail="Access denied")
    return document


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.execute(
        select(Project).filter(
            Project.project_id == project_id,
            Project.deleted_at.is_(None),
        )
    ).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_default_material_version_id_for_project(db: Session, project: Project) -> int | None:
    if project.material_id is None:
        return None
    return db.execute(
        select(MaterialVersion.material_version_id)
        .filter(MaterialVersion.material_id == project.material_id)
        .order_by(MaterialVersion.version_no.desc(), MaterialVersion.material_version_id.desc())
    ).scalar()


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, payload.project_id)
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only project owner can create documents")

    source: Optional[Document] = None
    if payload.source_document_id is not None:
        source = db.execute(
            select(Document).filter(
                Document.document_id == payload.source_document_id,
                Document.project_id == payload.project_id,
                Document.deleted_at.is_(None),
            )
        ).scalars().first()
        if not source:
            raise HTTPException(status_code=400, detail="source_document_id is invalid for this project")

    editor_user_id = payload.editor_user_id or project.user_id
    document = Document(
        project_id=payload.project_id,
        source_document_id=payload.source_document_id,
        editor_user_id=editor_user_id,
        material_version_id=(
            source.material_version_id
            if source is not None
            else _get_default_material_version_id_for_project(db, project)
        ),
        name=payload.name,
        notes=payload.notes,
    )
    db.add(document)
    db.flush()

    if source is not None:
        source_blocks = get_ordered_blocks(db, source.document_id)
        previous_new_id: Optional[UUID] = None
        for source_block in source_blocks:
            created = create_block(
                db=db,
                document_id=document.document_id,
                block_type_id=source_block.block_type_id,
                props=dict(source_block.props or {}),
                previous_block_id=previous_new_id,
                is_system=source_block.is_system,
                is_removable=source_block.is_removable,
                fixed_position=source_block.fixed_position,
            )
            previous_new_id = created.block_id
    else:
        # Keep system blocks initialized for non-copy documents.
        initialize_system_blocks(db, document.document_id)

    editable_version = create_initial_working_version(
        db,
        document,
        current_user=current_user,
        parent_version=get_latest_document_version(db, source.document_id) if source is not None else None,
        preprocess_requested=False,
    )
    operations_count = regenerate_document_operations(db, document.document_id)
    editable_version.operations_count = operations_count
    if source is not None and operations_count > 0:
        editable_version.run_switch_status = True
        editable_version.preprocess_status = PreprocessStatus.queued

    db.commit()
    db.refresh(document)
    if source is not None:
        notify_after_edit()
    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    project_id: Optional[int] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_deleted: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_project_ids = select(Project.project_id).filter(
        Project.user_id == current_user.user_id,
        Project.deleted_at.is_(None),
    )
    stmt = select(Document).filter(Document.project_id.in_(owned_project_ids))

    if project_id is not None:
        stmt = stmt.filter(Document.project_id == project_id)
    if not include_deleted:
        stmt = stmt.filter(Document.deleted_at.is_(None))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    documents = db.execute(
        stmt.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return check_document_access(db, document_id, current_user.user_id)


def _document_operations_response(
    document: Document,
    rows: list[DocumentOperation],
) -> DocumentOperationListResponse:
    return DocumentOperationListResponse(
        document_id=document.document_id,
        operations=[
            DocumentOperationResponse(
                document_operation_id=row.document_operation_id,
                document_id=row.document_id,
                source_block_id=row.source_block_id,
                source_block_type_id=row.source_block_type_id,
                operation_order=row.operation_order,
                operation_order_in_block=row.operation_order_in_block,
                operation_template_id=row.operation_template_id,
                operation_kind=row.operation_kind,
                label_snapshot=row.label_snapshot,
                operation_parameters=row.operation_parameters or {},
                target=row.operation_parameters or {},
                parse_status=row.parse_status,
                parse_errors=row.parse_errors or [],
                parse_warnings=row.parse_warnings or [],
            )
            for row in rows
        ],
    )


def _ordered_document_operation_rows(db: Session, document_id: int) -> list[DocumentOperation]:
    return db.execute(
        select(DocumentOperation)
        .filter(DocumentOperation.document_id == document_id)
        .order_by(DocumentOperation.operation_order.asc())
    ).scalars().all()


def _simulation_step_status_response(
    status_row: SimulationStepStatus | None,
) -> SimulationStepStatusResponse | None:
    if status_row is None:
        return None
    return SimulationStepStatusResponse(
        status=status_row.status.value,
        simulation_server_id=status_row.simulation_server_id,
        worker_name=status_row.worker_name,
        attempt_no=status_row.attempt_no,
        retry_count=status_row.retry_count,
        cancel_requested=status_row.cancel_requested,
        simulation_percent=status_row.simulation_percent,
        simulation_expected_duration_seconds=status_row.simulation_expected_duration_seconds,
        queued_at=status_row.queued_at,
        started_at=status_row.started_at,
        heartbeat_at=status_row.heartbeat_at,
        finished_at=status_row.finished_at,
        runtime_artifacts=status_row.runtime_artifacts or {},
        last_error=status_row.last_error,
        error_payload=status_row.error_payload,
        updated_at=status_row.updated_at,
    )


def _simulation_step_response(step: SimulationStep) -> SimulationStepResponse:
    return SimulationStepResponse(
        document_operation_id=step.document_operation_id,
        document_version_id=step.document_version_id,
        execution_order=step.execution_order,
        source_block_id=step.source_block_id,
        operation_template_id=step.operation_template_id,
        operation_kind=step.operation_kind,
        operation_label_snapshot=step.operation_label_snapshot,
        preprocess_ready=step.preprocess_ready,
        block_name_snapshot=step.block_name_snapshot,
        library_name_snapshot=step.library_name_snapshot,
        material_version_id=step.material_version_id,
        press_id=step.press_id,
        press_mode_id=step.press_mode_id,
        die_assembly_id=step.die_assembly_id,
        top_die_id=step.top_die_id,
        bottom_die_id=step.bottom_die_id,
        left_die_id=step.left_die_id,
        right_die_id=step.right_die_id,
        pre_input=step.pre_input or {},
        pre_output=step.pre_output or {},
        initial_geometry=step.initial_geometry,
        final_geometry=step.final_geometry,
        calculations=step.calculations or {},
        accumulated_time_start_seconds=step.accumulated_time_start_seconds,
        duration_seconds=step.duration_seconds,
        accumulated_time_stop_seconds=step.accumulated_time_stop_seconds,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


def _simulation_step_diagnostics_response(step: SimulationStep) -> SimulationStepDiagnosticsResponse:
    status_row = step.status
    search_terms = [f"document_operation_id={step.document_operation_id}"]
    if step.operation_template_id:
        search_terms.append(f"operation_template_id={step.operation_template_id}")
    if step.source_block_id is not None:
        search_terms.append(f"source_block_id={step.source_block_id}")
    related_log_query = {
        "service": "pre",
        "search_terms": search_terms,
        "document_operation_id": step.document_operation_id,
        "document_version_id": step.document_version_id,
        "execution_order": step.execution_order,
        "operation_template_id": step.operation_template_id,
    }
    if step.source_block_id is not None:
        related_log_query["source_block_id"] = str(step.source_block_id)
    if status_row is not None and status_row.worker_name:
        related_log_query["worker_name"] = status_row.worker_name

    api_messages = [
        {
            "severity": "info",
            "message": "This response intentionally separates simulation_steps output from simulation_step_status runtime state.",
        }
    ]
    calculations = step.calculations or {}
    if isinstance(calculations.get("preprocessor_error"), str):
        api_messages.append(
            {
                "severity": "error",
                "message": calculations["preprocessor_error"],
                "source": "simulation_steps.calculations.preprocessor_error",
            }
        )
    if isinstance(calculations.get("preprocessor_error_details"), dict):
        api_messages.append(
            {
                "severity": "error",
                "message": str(
                    calculations["preprocessor_error_details"].get("message")
                    or "Geometry validation failed"
                ),
                "source": "simulation_steps.calculations.preprocessor_error_details",
                "details": calculations["preprocessor_error_details"],
            }
        )
    if status_row is not None and status_row.last_error:
        api_messages.append(
            {
                "severity": "error",
                "message": status_row.last_error,
                "source": "simulation_step_status.last_error",
            }
        )

    return SimulationStepDiagnosticsResponse(
        response_sources={
            "simulation_step": "simulation_steps",
            "simulation_step_status": "simulation_step_status",
            "diagnostics": "API-composed troubleshooting metadata",
        },
        related_log_query=related_log_query,
        api_messages=api_messages,
    )


def _document_simulation_step_response(*, step: SimulationStep) -> DocumentSimulationStepResponse:
    return DocumentSimulationStepResponse(
        simulation_step=_simulation_step_response(step),
        simulation_step_status=_simulation_step_status_response(step.status),
        diagnostics=_simulation_step_diagnostics_response(step),
    )


def _get_simulation_step_for_document(
    *,
    db: Session,
    document_id: int,
    document_operation_id: int,
) -> SimulationStep | None:
    return db.execute(
        select(SimulationStep)
        .join(
            DocumentVersion,
            DocumentVersion.document_version_id == SimulationStep.document_version_id,
        )
        .filter(
            DocumentVersion.document_id == document_id,
            SimulationStep.document_operation_id == document_operation_id,
        )
    ).scalars().first()


@router.get("/{document_id}/operations", response_model=DocumentOperationListResponse)
def list_document_operations(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    rows = _ordered_document_operation_rows(db, document.document_id)
    needs_regeneration = (
        not any(row.operation_template_id == DOCUMENT_INITIAL_DATA_TEMPLATE_ID for row in rows)
        or any(
            row.operation_template_id == FURNACE_TEMPLATE_ID
            and (
                not isinstance(row.operation_parameters, dict)
                or "temperature_program" not in row.operation_parameters
            )
            for row in rows
        )
    )
    if needs_regeneration:
        try:
            assert_document_editable(db, document.document_id)
        except WorkflowCommandError:
            pass
        else:
            regenerate_document_operations(db, document.document_id)
            db.commit()
            rows = _ordered_document_operation_rows(db, document.document_id)

    return _document_operations_response(document, rows)


@router.get("/{document_id}/simulation-steps", response_model=DocumentSimulationStepListResponse)
def list_document_simulation_steps(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    steps = db.execute(
        select(SimulationStep)
        .join(
            DocumentVersion,
            DocumentVersion.document_version_id == SimulationStep.document_version_id,
        )
        .filter(DocumentVersion.document_id == document.document_id)
        .order_by(SimulationStep.execution_order.asc(), SimulationStep.document_operation_id.asc())
    ).scalars().all()
    return DocumentSimulationStepListResponse(
        document_id=document.document_id,
        steps=[
            _document_simulation_step_response(step=step)
            for step in steps
        ],
    )


@router.get(
    "/{document_id}/simulation-steps/{document_operation_id}/surface",
    response_model=DocumentSimulationStepSurfaceResponse,
)
def get_document_simulation_step_surface(
    document_id: int,
    document_operation_id: int,
    max_outline_points: int = Query(default=128, ge=8, le=512),
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    step = _get_simulation_step_for_document(
        db=db,
        document_id=document.document_id,
        document_operation_id=document_operation_id,
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Simulation step not found")

    try:
        generated = ensure_surface_artifacts_for_step(
            step,
            document_id=document.document_id,
            max_outline_points=max_outline_points,
            force=force,
        )
    except SurfaceMeshError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    step.calculations = {
        **(step.calculations or {}),
        "surface_artifacts": generated.summary,
    }
    db.commit()

    artifacts = with_surface_artifact_urls(
        generated.summary,
        document_id=document.document_id,
        document_operation_id=step.document_operation_id,
    ).get("artifacts", {})

    return DocumentSimulationStepSurfaceResponse(
        document_id=document.document_id,
        document_operation_id=step.document_operation_id,
        initial=generated.meshes["initial"].to_payload() if "initial" in generated.meshes else None,
        final=generated.meshes["final"].to_payload() if "final" in generated.meshes else None,
        artifacts=artifacts,
        source=str(generated.summary.get("source") or "legacy_preprocessor_trimesh"),
    )


@router.get("/{document_id}/simulation-steps/{document_operation_id}/surface/artifacts/{kind}/{artifact_format}")
def get_document_simulation_step_surface_artifact(
    document_id: int,
    document_operation_id: int,
    kind: str,
    artifact_format: str,
    max_outline_points: int = Query(default=128, ge=8, le=512),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if kind not in {"initial", "final"}:
        raise HTTPException(status_code=400, detail="kind must be 'initial' or 'final'")
    if artifact_format not in {"ply", "json", "stl"}:
        raise HTTPException(status_code=400, detail="artifact_format must be 'ply', 'json', or 'stl'")

    document = check_document_access(db, document_id, current_user.user_id)
    step = _get_simulation_step_for_document(
        db=db,
        document_id=document.document_id,
        document_operation_id=document_operation_id,
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Simulation step not found")

    try:
        generated = ensure_surface_artifacts_for_step(
            step,
            document_id=document.document_id,
            max_outline_points=max_outline_points,
        )
    except SurfaceMeshError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if kind not in generated.meshes:
        raise HTTPException(status_code=404, detail=f"{kind} surface artifact is not available")
    artifacts = generated.summary.get("artifacts") if isinstance(generated.summary, dict) else None
    artifact = artifacts.get(kind) if isinstance(artifacts, dict) else None
    files = artifact.get("files") if isinstance(artifact, dict) else None
    if not isinstance(files, dict) or artifact_format not in files:
        raise HTTPException(
            status_code=404,
            detail=f"{kind} surface artifact format {artifact_format!r} is not available",
        )

    path = surface_artifact_abs_path(step, kind, artifact_format)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Surface artifact file is missing: {path}")
    filename = f"document_{document.document_id}_operation_{step.document_operation_id}_{kind}_surface.{artifact_format}"
    media_type = {
        "json": "application/json",
        "stl": "model/stl",
        "ply": "application/octet-stream",
    }[artifact_format]
    return FileResponse(path, media_type=media_type, filename=filename)


@router.post("/{document_id}/simulation-steps/preprocess", response_model=DocumentPreprocessQueueResponse)
def queue_document_simulation_steps_preprocess(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    try:
        version, operations_count, queued = queue_document_preprocessing(
            db,
            document,
            current_user=current_user,
            regenerate_operations_before_queue=False,
        )
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    notify_after_edit()
    return DocumentPreprocessQueueResponse(
        document_id=document.document_id,
        document_version_id=version.document_version_id,
        preprocess_status=version.preprocess_status.value,
        operations_count=operations_count,
        queued=queued,
        message=(
            "Preprocessor is already running for this document."
            if not queued
            else "Preprocessor run queued."
        ),
    )


@router.post("/{document_id}/operations/regenerate", response_model=DocumentOperationListResponse)
def regenerate_document_operations_endpoint(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    try:
        assert_document_editable(db, document.document_id)
        regenerate_document_operations(db, document.document_id)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = _ordered_document_operation_rows(db, document.document_id)
    return _document_operations_response(document, rows)


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    try:
        assert_document_editable(db, document.document_id)
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(document, key, value)
        document.updated_at = datetime.utcnow()
        editable_version = create_initial_working_version(
            db,
            document,
            current_user=current_user,
            preprocess_requested=False,
        )
        editable_version.last_modified = document.updated_at
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    document.deleted_at = datetime.utcnow()
    db.commit()


@router.post("/{document_id}/restore", response_model=DocumentResponse)
def restore_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    document.deleted_at = None
    document.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(document)
    return document


@router.post("/{document_id}/copy", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def copy_document(
    document_id: int,
    payload: DocumentCopyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = check_document_access(db, document_id, current_user.user_id)
    project = _get_project_or_404(db, source.project_id)
    parent_version = get_latest_document_version(db, source.document_id)

    copied = Document(
        project_id=source.project_id,
        source_document_id=source.document_id,
        editor_user_id=payload.editor_user_id or source.editor_user_id or project.user_id,
        material_version_id=source.material_version_id,
        name=payload.name or f"{source.name} (copy)",
        notes=payload.notes if payload.notes is not None else source.notes,
    )
    db.add(copied)
    db.flush()

    ordered_blocks = get_ordered_blocks(db, source.document_id)
    previous_new_id: Optional[UUID] = None
    for source_block in ordered_blocks:
        created = create_block(
            db=db,
            document_id=copied.document_id,
            block_type_id=source_block.block_type_id,
            props=dict(source_block.props or {}),
            previous_block_id=previous_new_id,
            is_system=source_block.is_system,
            is_removable=source_block.is_removable,
            fixed_position=source_block.fixed_position,
        )
        previous_new_id = created.block_id

    editable_version = create_initial_working_version(
        db,
        copied,
        current_user=current_user,
        parent_version=parent_version,
        preprocess_requested=False,
    )
    operations_count = regenerate_document_operations(db, copied.document_id)
    editable_version.operations_count = operations_count
    if operations_count > 0:
        editable_version.run_switch_status = True
        editable_version.preprocess_status = PreprocessStatus.queued

    db.commit()
    db.refresh(copied)
    notify_after_edit()
    return copied


def _lineage_ancestors(db: Session, document: Document) -> List[DocumentLineageNode]:
    ancestors: List[DocumentLineageNode] = []
    current = document
    while current.source_document_id is not None:
        parent = db.execute(
            select(Document).filter(Document.document_id == current.source_document_id)
        ).scalars().first()
        if not parent:
            break
        ancestors.append(DocumentLineageNode.model_validate(parent))
        current = parent
    return ancestors


def _lineage_descendants(db: Session, root_document_id: int) -> List[DocumentLineageNode]:
    descendants: List[DocumentLineageNode] = []
    frontier = [root_document_id]
    while frontier:
        current_id = frontier.pop(0)
        children = db.execute(
            select(Document).filter(Document.source_document_id == current_id)
        ).scalars().all()
        for child in children:
            descendants.append(DocumentLineageNode.model_validate(child))
            frontier.append(child.document_id)
    return descendants


@router.get("/{document_id}/lineage", response_model=DocumentLineageResponse)
def get_document_lineage(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    return DocumentLineageResponse(
        target_document_id=document.document_id,
        ancestors=_lineage_ancestors(db, document),
        descendants=_lineage_descendants(db, document.document_id),
    )


@router.get("/{document_id}/diff/{other_document_id}", response_model=DocumentDiffResponse)
def diff_documents(
    document_id: int,
    other_document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    left = check_document_access(db, document_id, current_user.user_id)
    right = check_document_access(db, other_document_id, current_user.user_id)

    left_blocks = get_ordered_blocks(db, left.document_id)
    right_blocks = get_ordered_blocks(db, right.document_id)

    max_len = max(len(left_blocks), len(right_blocks))
    changes: List[BlockDiffEntry] = []
    for idx in range(max_len):
        lb = left_blocks[idx] if idx < len(left_blocks) else None
        rb = right_blocks[idx] if idx < len(right_blocks) else None

        if lb is None and rb is not None:
            changes.append(
                BlockDiffEntry(
                    index=idx,
                    change_type="added",
                    right_block_id=rb.block_id,
                    right_block_type_id=rb.block_type_id,
                    right_props=rb.props,
                )
            )
            continue

        if rb is None and lb is not None:
            changes.append(
                BlockDiffEntry(
                    index=idx,
                    change_type="removed",
                    left_block_id=lb.block_id,
                    left_block_type_id=lb.block_type_id,
                    left_props=lb.props,
                )
            )
            continue

        assert lb is not None and rb is not None
        if lb.block_type_id != rb.block_type_id or (lb.props or {}) != (rb.props or {}):
            changes.append(
                BlockDiffEntry(
                    index=idx,
                    change_type="modified",
                    left_block_id=lb.block_id,
                    right_block_id=rb.block_id,
                    left_block_type_id=lb.block_type_id,
                    right_block_type_id=rb.block_type_id,
                    left_props=lb.props,
                    right_props=rb.props,
                )
            )

    return DocumentDiffResponse(
        left_document_id=left.document_id,
        right_document_id=right.document_id,
        left_name=left.name,
        right_name=right.name,
        total_changes=len(changes),
        changes=changes,
    )


@router.post("/{document_id}/sessions/start", response_model=EditSessionResponse, status_code=status.HTTP_201_CREATED)
def start_edit_session(
    document_id: int,
    payload: EditSessionStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)

    editor_user_id = payload.editor_user_id or current_user.user_id
    if editor_user_id != current_user.user_id:
        project = _get_project_or_404(db, document.project_id)
        if project.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Only owner can start session for other users")

    session = DocumentEditSession(
        document_id=document.document_id,
        editor_user_id=editor_user_id,
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{document_id}/sessions/{session_id}/end", response_model=EditSessionResponse)
def end_edit_session(
    document_id: int,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_document_access(db, document_id, current_user.user_id)
    session = db.execute(
        select(DocumentEditSession).filter(
            DocumentEditSession.session_id == session_id,
            DocumentEditSession.document_id == document_id,
        )
    ).scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.ended_at is None:
        session.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    return session


@router.get("/{document_id}/sessions", response_model=EditSessionListResponse)
def list_edit_sessions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_document_access(db, document_id, current_user.user_id)
    sessions = db.execute(
        select(DocumentEditSession)
        .filter(DocumentEditSession.document_id == document_id)
        .order_by(DocumentEditSession.started_at.desc())
    ).scalars().all()
    return EditSessionListResponse(
        sessions=[EditSessionResponse.model_validate(session) for session in sessions],
        total=len(sessions),
    )

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.document.document import Document, DocumentVersion
from app.models.project import Project
from app.models.server import Server, ServerType
from app.models.user import User
from app.routers.document import check_document_access
from app.schemas import (
    DocumentForkRequest,
    DocumentQueueRequest,
    DocumentResponse,
    DocumentVersionPriorityUpdate,
    WorkflowDocumentStatusListResponse,
    WorkflowDocumentStatusRow,
    WorkflowSimulationReorderRequest,
    WorkflowSimulationReorderResponse,
    WorkflowSimulationStatusListResponse,
    WorkflowSimulationStatusRow,
    WorkflowSolverPcStatusListResponse,
    WorkflowSolverPcStatusRow,
    DocumentWorkflowResponse,
)
from app.services.workflow_commands import (
    WorkflowCommandError,
    build_workflow_snapshot,
    cancel_run,
    fork_fixed_document,
    get_document_version_or_none,
    get_latest_document_version,
    notify_after_run_command,
    queue_document_for_simulation,
    resume_run,
    retry_run,
    update_run_priority,
    pause_run,
)


router = APIRouter(tags=["workflow"])


def _queue_sort_key(version: DocumentVersion) -> tuple[int, int, int]:
    is_running_rank = 0 if version.simulation_status.value == "run" else 1
    priority = int(version.simulation_priority or 32767)
    return (is_running_rank, priority, version.document_version_id)


def _build_queue_positions(versions: list[DocumentVersion]) -> dict[int, int]:
    queued_versions = [
        version
        for version in versions
        if version.is_editable is False
        and version.run_switch_is_active
        and version.simulation_status.value not in {"done", "error"}
    ]
    ordered = sorted(queued_versions, key=_queue_sort_key)
    return {
        version.document_version_id: index + 1
        for index, version in enumerate(ordered)
    }


def _get_accessible_version(
    db: Session,
    document_version_id: int,
    user_id: int,
) -> DocumentVersion:
    version = get_document_version_or_none(db, document_version_id)
    if version is None or version.document_id is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    check_document_access(db, version.document_id, user_id)
    return version


def _build_workflow_response(
    document_id: int,
    version: DocumentVersion | None,
) -> DocumentWorkflowResponse:
    snapshot = build_workflow_snapshot(version)
    return DocumentWorkflowResponse(
        document_id=document_id,
        document_version_id=version.document_version_id if version is not None else None,
        parent_document_version_id=version.parent_document_version_id if version is not None else None,
        document_fixed=snapshot.document_fixed,
        workflow_state=snapshot.workflow_state,
        preprocess_requested=snapshot.preprocess_requested,
        automation_active=snapshot.automation_active,
        is_editable=version.is_editable if version is not None else None,
        simulation_status=version.simulation_status if version is not None else None,
        document_priority_enum=version.document_priority_enum if version is not None else None,
        simulation_priority=version.simulation_priority if version is not None else None,
        operations_count=version.operations_count if version is not None else None,
        simulation_percent=version.simulation_percent if version is not None else None,
        simulation_expected_duration_days=(
            version.simulation_expected_duration_days if version is not None else None
        ),
        simulation_server_id=version.simulation_server_id if version is not None else None,
        created_at=version.created_at if version is not None else None,
        last_modified=version.last_modified if version is not None else None,
        ran_at=version.ran_at if version is not None else None,
        finished_at=version.finished_at if version is not None else None,
    )


def _list_all_documents_with_projects(db: Session) -> list[tuple[Document, Project, User]]:
    rows = db.execute(
        select(Document, Project, User)
        .join(Project, Project.project_id == Document.project_id)
        .join(User, User.user_id == Project.user_id)
        .filter(Document.deleted_at.is_(None), Project.deleted_at.is_(None))
        .order_by(Document.created_at.desc(), Document.document_id.desc())
    ).all()
    return [(document, project, owner) for document, project, owner in rows]


def _list_all_versions(db: Session) -> list[DocumentVersion]:
    return list(
        db.execute(
            select(DocumentVersion).order_by(DocumentVersion.document_version_id.desc())
        ).scalars().all()
    )


@router.get("/workflow/documents", response_model=WorkflowDocumentStatusListResponse)
def list_document_statuses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del current_user
    document_rows = _list_all_documents_with_projects(db)
    versions = _list_all_versions(db)
    latest_version_by_document_id: dict[int, DocumentVersion] = {}
    for version in versions:
        if version.document_id is None:
            continue
        latest_version_by_document_id.setdefault(version.document_id, version)
    queue_positions = _build_queue_positions(versions)

    items = [
        WorkflowDocumentStatusRow(
            document_id=document.document_id,
            document_name=document.name,
            project_id=project.project_id,
            project_name=project.name,
            owner_user_id=owner.user_id,
            owner_login=owner.login,
            source_document_id=document.source_document_id,
            document_version_id=version.document_version_id if version is not None else None,
            workflow_state=snapshot.workflow_state,
            document_fixed=snapshot.document_fixed,
            preprocess_requested=snapshot.preprocess_requested,
            automation_active=snapshot.automation_active,
            is_editable=version.is_editable if version is not None else None,
            simulation_status=version.simulation_status if version is not None else None,
            simulation_priority=version.simulation_priority if version is not None else None,
            queue_position=(
                queue_positions.get(version.document_version_id)
                if version is not None
                else None
            ),
            operations_count=version.operations_count if version is not None else None,
            simulation_percent=version.simulation_percent if version is not None else None,
            last_modified=version.last_modified if version is not None else None,
        )
        for document, project, owner in document_rows
        for version in [latest_version_by_document_id.get(document.document_id)]
        for snapshot in [build_workflow_snapshot(version)]
    ]
    return WorkflowDocumentStatusListResponse(documents=items)


@router.get("/workflow/simulations", response_model=WorkflowSimulationStatusListResponse)
def list_simulation_statuses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del current_user
    versions = _list_all_versions(db)
    queue_positions = _build_queue_positions(versions)
    document_rows = _list_all_documents_with_projects(db)
    document_map = {document.document_id: (document, project, owner) for document, project, owner in document_rows}
    server_name_by_id = {
        server.id: server.name
        for server in db.execute(select(Server)).scalars().all()
    }

    items: list[WorkflowSimulationStatusRow] = []
    for version in versions:
        if version.document_id is None or version.is_editable:
            continue
        document_bundle = document_map.get(version.document_id)
        if document_bundle is None:
            continue
        document, project, owner = document_bundle
        snapshot = build_workflow_snapshot(version)
        items.append(
            WorkflowSimulationStatusRow(
                document_version_id=version.document_version_id,
                document_id=document.document_id,
                document_name=document.name,
                version_name=version.name,
                project_id=project.project_id,
                project_name=project.name,
                owner_user_id=owner.user_id,
                owner_login=owner.login,
                workflow_state=snapshot.workflow_state,
                document_fixed=snapshot.document_fixed,
                preprocess_requested=snapshot.preprocess_requested,
                automation_active=snapshot.automation_active,
                is_editable=bool(version.is_editable),
                simulation_status=version.simulation_status,
                simulation_priority=version.simulation_priority,
                queue_position=queue_positions.get(version.document_version_id),
                operations_count=version.operations_count,
                simulation_percent=version.simulation_percent,
                simulation_expected_duration_days=version.simulation_expected_duration_days,
                simulation_server_id=version.simulation_server_id,
                simulation_server_name=server_name_by_id.get(version.simulation_server_id)
                if version.simulation_server_id is not None
                else None,
                last_modified=version.last_modified,
                ran_at=version.ran_at,
                finished_at=version.finished_at,
            )
        )

    items.sort(
        key=lambda item: (
            item.queue_position is None,
            item.queue_position or 32767,
            -item.document_version_id,
        )
    )
    return WorkflowSimulationStatusListResponse(simulations=items)


@router.get("/workflow/solver-pcs", response_model=WorkflowSolverPcStatusListResponse)
def list_solver_pc_statuses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del current_user
    servers = list(
        db.execute(
            select(Server)
            .filter(Server.type == ServerType.simulation)
            .order_by(Server.hostname.asc(), Server.name.asc())
        ).scalars().all()
    )
    versions_by_id = {
        version.document_version_id: version
        for version in _list_all_versions(db)
    }
    document_name_by_id = {
        document.document_id: document.name
        for document, _project, _owner in _list_all_documents_with_projects(db)
    }

    items: list[WorkflowSolverPcStatusRow] = []
    for server in servers:
        version = (
            versions_by_id.get(server.document_version_id)
            if server.document_version_id is not None
            else None
        )
        document_name = (
            document_name_by_id.get(version.document_id)
            if version is not None and version.document_id is not None
            else None
        )
        worker_state = "offline"
        if server.is_active:
            worker_state = "busy" if version is not None else "idle"

        items.append(
            WorkflowSolverPcStatusRow(
                server_id=server.id,
                name=server.name,
                hostname=server.hostname,
                ip=server.ip,
                is_active=bool(server.is_active),
                worker_state=worker_state,
                document_version_id=version.document_version_id if version is not None else None,
                document_name=document_name,
                version_name=version.name if version is not None else None,
                time_started=server.time_started,
                time_updated=server.time_updated,
                time_finished=server.time_finished,
                version=server.version,
                cpu_count=server.cpu_count,
                max_threads_count=server.max_threads_count,
                ram_free_size_gb=server.ram_free_size_gb,
                hdd_free_size_gb=server.hdd_free_size_gb,
                timeout_counter=server.timeout_counter,
            )
        )

    return WorkflowSolverPcStatusListResponse(solver_pcs=items)


@router.patch("/workflow/simulations/reorder", response_model=WorkflowSimulationReorderResponse)
def reorder_simulation_queue(
    payload: WorkflowSimulationReorderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del current_user
    ordered_ids = payload.ordered_document_version_ids
    if not ordered_ids:
        raise HTTPException(status_code=400, detail="ordered_document_version_ids must not be empty")

    versions = list(
        db.execute(
            select(DocumentVersion).filter(DocumentVersion.document_version_id.in_(ordered_ids))
        ).scalars().all()
    )
    version_by_id = {version.document_version_id: version for version in versions}
    missing_ids = [version_id for version_id in ordered_ids if version_id not in version_by_id]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Document versions not found: {missing_ids}")

    for version_id in ordered_ids:
        version = version_by_id[version_id]
        if version.is_editable:
            raise HTTPException(status_code=400, detail="Only fixed simulation runs can be reordered")

    for index, version_id in enumerate(ordered_ids, start=1):
        version = version_by_id[version_id]
        version.simulation_priority = index
        version.last_modified = version.last_modified or version.created_at

    db.commit()
    notify_after_run_command()
    return WorkflowSimulationReorderResponse(updated_document_version_ids=ordered_ids)


@router.get("/documents/{document_id}/workflow", response_model=DocumentWorkflowResponse)
def get_document_workflow(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    version = get_latest_document_version(db, document.document_id)
    return _build_workflow_response(document.document_id, version)


@router.post(
    "/documents/{document_id}/workflow/queue",
    response_model=DocumentWorkflowResponse,
    status_code=status.HTTP_200_OK,
)
def queue_document(
    document_id: int,
    payload: DocumentQueueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    try:
        version = queue_document_for_simulation(
            db,
            document,
            current_user=current_user,
            simulation_priority=payload.simulation_priority,
            document_priority=payload.document_priority_enum,
        )
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(version)
    notify_after_run_command()
    return _build_workflow_response(document.document_id, version)


@router.post(
    "/documents/{document_id}/workflow/fork",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def fork_document(
    document_id: int,
    payload: DocumentForkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source_document = check_document_access(db, document_id, current_user.user_id)
    try:
        forked = fork_fixed_document(
            db,
            source_document,
            name=payload.name or f"{source_document.name} (fork)",
            notes=payload.notes,
            editor_user_id=payload.editor_user_id,
            current_user=current_user,
        )
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(forked)
    notify_after_run_command()
    return forked


@router.patch(
    "/document-versions/{document_version_id}/workflow/priority",
    response_model=DocumentWorkflowResponse,
)
def update_priority(
    document_version_id: int,
    payload: DocumentVersionPriorityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = _get_accessible_version(db, document_version_id, current_user.user_id)
    try:
        version = update_run_priority(
            version,
            simulation_priority=payload.simulation_priority,
            document_priority=payload.document_priority_enum,
        )
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(version)
    notify_after_run_command()
    return _build_workflow_response(version.document_id, version)


@router.post(
    "/document-versions/{document_version_id}/workflow/pause",
    response_model=DocumentWorkflowResponse,
)
def pause_version_run(
    document_version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = _get_accessible_version(db, document_version_id, current_user.user_id)
    try:
        version = pause_run(version)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(version)
    notify_after_run_command()
    return _build_workflow_response(version.document_id, version)


@router.post(
    "/document-versions/{document_version_id}/workflow/resume",
    response_model=DocumentWorkflowResponse,
)
def resume_version_run(
    document_version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = _get_accessible_version(db, document_version_id, current_user.user_id)
    try:
        version = resume_run(version)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(version)
    notify_after_run_command()
    return _build_workflow_response(version.document_id, version)


@router.post(
    "/document-versions/{document_version_id}/workflow/cancel",
    response_model=DocumentWorkflowResponse,
)
def cancel_version_run(
    document_version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = _get_accessible_version(db, document_version_id, current_user.user_id)
    try:
        version = cancel_run(version)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(version)
    notify_after_run_command()
    return _build_workflow_response(version.document_id, version)


@router.post(
    "/document-versions/{document_version_id}/workflow/retry",
    response_model=DocumentWorkflowResponse,
)
def retry_version_run(
    document_version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = _get_accessible_version(db, document_version_id, current_user.user_id)
    try:
        version = retry_run(version)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(version)
    notify_after_run_command()
    return _build_workflow_response(version.document_id, version)

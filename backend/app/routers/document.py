from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.document.block import Block
from app.models.document.document import Document, DocumentEditSession
from app.models.project import Project
from app.models.user import User
from app.schemas import (
    BlockDiffEntry,
    DocumentCopyRequest,
    DocumentCreate,
    DocumentDiffResponse,
    DocumentLineageNode,
    DocumentLineageResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    EditSessionListResponse,
    EditSessionResponse,
    EditSessionStartRequest,
)
from app.services.block_service import create_block, get_ordered_blocks
from app.services.block_type_service import initialize_system_blocks

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

    db.commit()
    db.refresh(document)
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


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(document, key, value)
    document.updated_at = datetime.utcnow()
    db.commit()
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

    copied = Document(
        project_id=source.project_id,
        source_document_id=source.document_id,
        editor_user_id=payload.editor_user_id or source.editor_user_id or project.user_id,
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

    db.commit()
    db.refresh(copied)
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

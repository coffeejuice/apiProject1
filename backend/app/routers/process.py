from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, select, func
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models.document.process import Process, ProcessACL, Role
from app.models.user import User
from app.schemas import (
    ProcessCreate, ProcessUpdate, ProcessResponse,
    ProcessListResponse
)
from app.auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

def check_process_access(
    db: Session,
    process_id: int,
    user_id: int,
    required_role: Optional[Role] = None
) -> Process:
    """Check if user has access to document"""
    doc = db.execute(select(Process).filter(Process.process_id == process_id)).scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Process not found")

    # Owner has full access
    if doc.user_id == user_id:
        return doc

    # Check ACL
    acl = db.execute(select(ProcessACL).filter(
        ProcessACL.process_id == process_id,
        ProcessACL.user_id == user_id
    )).scalars().first()

    if not acl:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check role hierarchy: owner > editor > viewer
    role_hierarchy = {Role.owner: 3, Role.editor: 2, Role.viewer: 1}
    if required_role and role_hierarchy.get(acl.role, 0) < role_hierarchy.get(required_role, 0):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return doc

@router.post("", response_model=ProcessResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    doc_data: ProcessCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        doc = Process(
            **doc_data.model_dump(exclude={"user_id"}),
            user_id=current_user.user_id
        )
        db.add(doc)
        db.flush()  # Get process_id before creating blocks

        # Auto-create system blocks
        from app.services.block_type_service import initialize_system_blocks
        initialize_system_blocks(db, doc.process_id)

        db.commit()
        db.refresh(doc)
        return doc
    except Exception as e:
        db.rollback()
        import traceback
        print(f"Error creating document: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=ProcessListResponse)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_deleted: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get documents user owns or has access to
    stmt = select(Process).filter(
        or_(
            Process.user_id == current_user.user_id,
            Process.process_id.in_(
                select(ProcessACL.process_id).filter(
                    ProcessACL.user_id == current_user.user_id
                )
            )
        )
    )

    if not include_deleted:
        stmt = stmt.filter(Process.deleted_at == None)

    # Get total count
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    
    # Get paginated documents
    documents = db.execute(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    return ProcessListResponse(
        documents=list(documents),
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{process_id}", response_model=ProcessResponse)
def get_document(
    process_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_process_access(db, process_id, current_user.user_id)
    return doc

@router.patch("/{process_id}", response_model=ProcessResponse)
def update_document(
    process_id: int,
    doc_data: ProcessUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_process_access(db, process_id, current_user.user_id, Role.editor)

    update_data = doc_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(doc, key, value)

    db.commit()
    db.refresh(doc)
    return doc

@router.delete("/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    process_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_process_access(db, process_id, current_user.user_id, Role.editor)
    doc.deleted_at = datetime.utcnow()
    db.commit()

@router.post("/{process_id}/restore", response_model=ProcessResponse)
def restore_document(
    process_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_process_access(db, process_id, current_user.user_id, Role.editor)
    doc.deleted_at = None
    db.commit()
    db.refresh(doc)
    return doc

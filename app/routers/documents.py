from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models import Document, DocumentACL, Role, User
from app.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentListResponse
)
from app.auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

def check_document_access(
    db: Session,
    document_id: UUID,
    user_id: UUID,
    required_role: Optional[Role] = None
) -> Document:
    """Check if user has access to document"""
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Owner has full access
    if doc.owner_id == user_id:
        return doc

    # Check ACL
    acl = db.query(DocumentACL).filter(
        DocumentACL.document_id == document_id,
        DocumentACL.user_id == user_id
    ).first()

    if not acl:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check role hierarchy: owner > editor > viewer
    role_hierarchy = {Role.owner: 3, Role.editor: 2, Role.viewer: 1}
    if required_role and role_hierarchy.get(acl.role, 0) < role_hierarchy.get(required_role, 0):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return doc

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    doc_data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = Document(
        owner_id=current_user.user_id,
        title=doc_data.title
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.get("", response_model=DocumentListResponse)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_deleted: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get documents user owns or has access to
    query = db.query(Document).filter(
        or_(
            Document.owner_id == current_user.user_id,
            Document.document_id.in_(
                db.query(DocumentACL.document_id).filter(
                    DocumentACL.user_id == current_user.user_id
                )
            )
        )
    )

    if not include_deleted:
        query = query.filter(Document.deleted_at == None)

    total = query.count()
    documents = query.offset((page - 1) * page_size).limit(page_size).all()

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_document_access(db, document_id, current_user.user_id)
    return doc

@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: UUID,
    doc_data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_document_access(db, document_id, current_user.user_id, Role.editor)

    if doc_data.title:
        doc.title = doc_data.title

    db.commit()
    db.refresh(doc)
    return doc

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_document_access(db, document_id, current_user.user_id, Role.editor)
    doc.deleted_at = datetime.utcnow()
    db.commit()

@router.post("/{document_id}/restore", response_model=DocumentResponse)
def restore_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_document_access(db, document_id, current_user.user_id, Role.editor)
    doc.deleted_at = None
    db.commit()
    db.refresh(doc)
    return doc

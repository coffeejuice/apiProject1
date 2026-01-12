from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta
import secrets
from app.database import get_db
from app.models import User, DocumentACL, ShareLink, Role
from app.schemas import InviteRequest, ACLResponse, ShareLinkResponse, DocumentResponse
from app.auth import get_current_user
from app.routers.documents import check_document_access

router = APIRouter(prefix="/documents/{document_id}", tags=["sharing"])

@router.post("/invites", status_code=status.HTTP_201_CREATED)
def invite_user(
    document_id: UUID,
    invite: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only owner can invite
    doc = check_document_access(db, document_id, current_user.user_id)
    if doc.owner_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only owner can invite users")

    # Find user by email
    target_user = db.query(User).filter(User.email == invite.email).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already has access
    existing = db.query(DocumentACL).filter(
        DocumentACL.document_id == document_id,
        DocumentACL.user_id == target_user.user_id
    ).first()

    if existing:
        # Update role
        existing.role = invite.role
    else:
        # Create new ACL
        acl = DocumentACL(
            document_id=document_id,
            user_id=target_user.user_id,
            role=invite.role
        )
        db.add(acl)

    db.commit()
    return {"message": "User invited successfully"}

@router.get("/acl", response_model=List[ACLResponse])
def get_document_acl(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = check_document_access(db, document_id, current_user.user_id)
    acl_entries = db.query(DocumentACL).filter(DocumentACL.document_id == document_id).all()
    return acl_entries

@router.delete("/acl/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_access(
    document_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only owner can revoke
    doc = check_document_access(db, document_id, current_user.user_id)
    if doc.owner_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only owner can revoke access")

    acl = db.query(DocumentACL).filter(
        DocumentACL.document_id == document_id,
        DocumentACL.user_id == user_id
    ).first()

    if acl:
        db.delete(acl)
        db.commit()

@router.post("/share-links", response_model=ShareLinkResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    document_id: UUID,
    expires_days: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id)

    # Generate unique token
    token = secrets.token_urlsafe(32)

    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

    link = ShareLink(
        document_id=document_id,
        token=token,
        created_by=current_user.user_id,
        expires_at=expires_at
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.get("/share-links", response_model=List[ShareLinkResponse])
def list_share_links(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id)
    links = db.query(ShareLink).filter(ShareLink.document_id == document_id).all()
    return links

@router.delete("/share-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_share_link(
    document_id: UUID,
    link_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id)

    link = db.query(ShareLink).filter(
        ShareLink.link_id == link_id,
        ShareLink.document_id == document_id
    ).first()

    if link:
        db.delete(link)
        db.commit()

# Public share link endpoint
share_router = APIRouter(prefix="/share", tags=["sharing"])

@share_router.get("/{token}", response_model=DocumentResponse)
def access_shared_document(
    token: str,
    db: Session = Depends(get_db)
):
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")

    # Check expiration
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Share link expired")

    from app.models import Document
    doc = db.query(Document).filter(Document.document_id == link.document_id).first()
    return doc

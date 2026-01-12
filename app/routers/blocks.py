from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.database import get_db
from app.models import User
from app.schemas import BlockResponse, CommitRequest, CommitResponse
from app.auth import get_current_user
from app.routers.documents import check_document_access
from app.services.block_service import get_root_blocks, get_block_children
from app.services.commit_service import commit_operations
from app.models import Role

router = APIRouter(tags=["blocks"])

@router.get("/documents/{document_id}/blocks/root", response_model=List[BlockResponse])
def get_document_root_blocks(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id)
    blocks = get_root_blocks(db, document_id)
    return blocks

@router.get("/blocks/{block_id}/children", response_model=List[BlockResponse])
def get_block_children_route(
    block_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    children = get_block_children(db, block_id)
    if children:
        # Verify access to document
        check_document_access(db, children[0].document_id, current_user.user_id)
    return children

@router.post("/documents/{document_id}/commit", response_model=CommitResponse)
def commit_changes(
    document_id: UUID,
    commit_req: CommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check write access
    check_document_access(db, document_id, current_user.user_id, Role.editor)

    success, new_rev, conflicts = commit_operations(
        db=db,
        document_id=document_id,
        device_id=commit_req.device_id,
        client_batch_id=commit_req.client_batch_id,
        base_rev_number=commit_req.base_rev_number,
        ops=commit_req.ops,
        user_id=current_user.user_id
    )

    return CommitResponse(
        success=success,
        new_rev_number=new_rev,
        conflicts=conflicts
    )

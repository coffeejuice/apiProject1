from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.database import get_db
from app.models import User, Role
from app.schemas import BlockResponse, CommitRequest, CommitResponse
from app.auth import get_current_user
from app.routers.process import check_process_access
from app.services.block_service import get_root_blocks, get_block_children
from app.services.commit_service import commit_operations

router = APIRouter(tags=["blocks"])

@router.get("/documents/{process_id}/blocks/root", response_model=List[BlockResponse])
def get_document_root_blocks(
    process_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_process_access(db, process_id, current_user.user_id)
    blocks = get_root_blocks(db, process_id)
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
        check_process_access(db, children[0].process_id, current_user.user_id)
    return children

@router.post("/documents/{process_id}/commit", response_model=CommitResponse)
def commit_changes(
    process_id: int,
    commit_req: CommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check write access
    check_process_access(db, process_id, current_user.user_id, Role.editor)

    success, new_rev, conflicts = commit_operations(
        db=db,
        process_id=process_id,
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

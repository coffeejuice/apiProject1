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

@router.get("/documents/{process_id}/blocks/root")
def get_document_root_blocks(
    process_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_process_access(db, process_id, current_user.user_id)
    blocks = get_root_blocks(db, process_id)

    # Enrich blocks with handler data
    from app.services.block_type_service import enrich_block_data_for_frontend
    enriched_blocks = [enrich_block_data_for_frontend(db, block) for block in blocks]

    return enriched_blocks

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

    try:
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
    except ValueError as e:
        # Validation error - return user-friendly message
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected error
        import traceback
        print(f"Unexpected error in commit: {e}")
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

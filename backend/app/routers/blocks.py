from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.document.block import Block
from app.models.user import User
from app.routers.document import check_document_access
from app.schemas import (
    BlockCreate,
    BlockMove,
    BlockResponse,
    BlockUpdate,
    CommitRequest,
    CommitResponse,
)
from app.services.block_service import create_block, delete_block, get_root_blocks, move_block_after, update_block_props
from app.services.block_type_service import (
    can_delete_block,
    can_reorder_block,
    enrich_block_data_for_frontend,
    validate_block_constraints,
)
from app.services.commit_service import commit_operations

router = APIRouter(tags=["blocks"])


@router.get("/documents/{document_id}/blocks/root", response_model=List[BlockResponse])
def get_document_root_blocks(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_document_access(db, document_id, current_user.user_id)
    blocks = get_root_blocks(db, document_id)
    enriched = [enrich_block_data_for_frontend(db, block) for block in blocks]
    return [BlockResponse.model_validate(item) for item in enriched]


@router.post("/documents/{document_id}/blocks", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
def insert_block(
    document_id: int,
    payload: BlockCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_document_access(db, document_id, current_user.user_id)
    if not validate_block_constraints(db, document_id, payload.block_type_id):
        raise HTTPException(status_code=400, detail="Block constraints violated")

    block = create_block(
        db=db,
        document_id=document_id,
        block_type_id=payload.block_type_id,
        props=payload.props,
        previous_block_id=payload.previous_block_id,
    )
    db.commit()
    db.refresh(block)
    enriched = enrich_block_data_for_frontend(db, block)
    return BlockResponse.model_validate(enriched)


@router.patch("/blocks/{block_id}", response_model=BlockResponse)
def update_block(
    block_id: UUID,
    payload: BlockUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    check_document_access(db, block.document_id, current_user.user_id)

    updated = update_block_props(db, block_id, payload.props)
    if not updated:
        raise HTTPException(status_code=404, detail="Block not found")

    # Run block handler update hook when available.
    from app.models.document.block_types import get_block_type_handler

    handler = get_block_type_handler(updated.block_type_id)
    if handler:
        handler.on_update(db, updated.block_id, updated.document_id, updated.props)

    db.commit()
    db.refresh(updated)
    return BlockResponse.model_validate(enrich_block_data_for_frontend(db, updated))


@router.post("/blocks/{block_id}/move", response_model=BlockResponse)
def move_block(
    block_id: UUID,
    payload: BlockMove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    check_document_access(db, block.document_id, current_user.user_id)

    if not can_reorder_block(db, block_id):
        raise HTTPException(status_code=400, detail="Block has fixed position")

    moved = move_block_after(
        db=db,
        document_id=block.document_id,
        block_id=block_id,
        previous_block_id=payload.previous_block_id,
    )
    if not moved:
        raise HTTPException(status_code=404, detail="Block not found")

    db.commit()
    db.refresh(moved)
    return BlockResponse.model_validate(enrich_block_data_for_frontend(db, moved))


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_block(
    block_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    check_document_access(db, block.document_id, current_user.user_id)

    if not can_delete_block(db, block_id):
        raise HTTPException(status_code=400, detail="Block is not removable")

    from app.models.document.block_types import get_block_type_handler

    handler = get_block_type_handler(block.block_type_id)
    if handler:
        handler.on_delete(db, block_id, block.document_id)

    if not delete_block(db, block.document_id, block_id):
        raise HTTPException(status_code=404, detail="Block not found")
    db.commit()


@router.post("/documents/{document_id}/commit", response_model=CommitResponse)
def commit_changes(
    document_id: int,
    commit_req: CommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_document_access(db, document_id, current_user.user_id)
    success, message = commit_operations(
        db=db,
        document_id=document_id,
        ops=commit_req.ops,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return CommitResponse(success=True, message=message)

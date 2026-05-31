from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.document.block import Block
from app.models.document.document import Document
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
from app.services.block_service import create_block_or_bundle, delete_block_or_bundle, get_root_blocks, move_block_after, update_block_props
from app.services.block_type_service import (
    can_insert_block_after,
    can_delete_block,
    can_reorder_block,
    enrich_block_data_for_frontend,
    validate_block_constraints,
)
from app.services.commit_service import commit_operations
from app.services.document_operations import normalize_props_for_block_type, regenerate_document_operations
from app.services.operation_blocks import is_operation_block_type, sanitize_operation_props
from app.services.workflow_commands import (
    WorkflowCommandError,
    assert_document_editable,
    mark_document_edited,
    notify_after_edit,
)

router = APIRouter(tags=["blocks"])


def _get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


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
    document = check_document_access(db, document_id, current_user.user_id)
    try:
        assert_document_editable(db, document_id)
        if not validate_block_constraints(db, document_id, payload.block_type_id):
            raise HTTPException(status_code=400, detail="Block constraints violated")
        if not can_insert_block_after(db, document_id, payload.block_type_id, payload.previous_block_id):
            raise HTTPException(status_code=400, detail="Cannot insert before fixed system blocks")

        block = create_block_or_bundle(
            db=db,
            document_id=document_id,
            block_type_id=payload.block_type_id,
            props=normalize_props_for_block_type(payload.block_type_id, payload.props),
            previous_block_id=payload.previous_block_id,
        )
        mark_document_edited(db, document, current_user=current_user)
        regenerate_document_operations(db, document_id)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(block)
    notify_after_edit()
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
    document = check_document_access(db, block.document_id, current_user.user_id)

    try:
        assert_document_editable(db, block.document_id)
        props = (
            sanitize_operation_props(db, block.block_type_id, payload.props)
            if is_operation_block_type(db, block.block_type_id)
            else normalize_props_for_block_type(block.block_type_id, payload.props)
        )
        updated = update_block_props(db, block_id, props)
        if not updated:
            raise HTTPException(status_code=404, detail="Block not found")

        # Run block handler update hook when available.
        from app.models.document.block_types import get_block_type_handler

        handler = get_block_type_handler(updated.block_type_id)
        if handler:
            handler.on_update(db, updated.block_id, updated.document_id, updated.props)

        mark_document_edited(db, document, current_user=current_user)
        regenerate_document_operations(db, block.document_id)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(updated)
    notify_after_edit()
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
    document = check_document_access(db, block.document_id, current_user.user_id)

    try:
        assert_document_editable(db, block.document_id)
        if not can_reorder_block(db, block_id):
            raise HTTPException(status_code=400, detail="Block has fixed position")
        if not can_insert_block_after(db, block.document_id, block.block_type_id, payload.previous_block_id):
            raise HTTPException(status_code=400, detail="Cannot move before fixed system blocks")

        moved = move_block_after(
            db=db,
            document_id=block.document_id,
            block_id=block_id,
            previous_block_id=payload.previous_block_id,
        )
        if not moved:
            raise HTTPException(status_code=404, detail="Block not found")

        mark_document_edited(db, document, current_user=current_user)
        regenerate_document_operations(db, block.document_id)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(moved)
    notify_after_edit()
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
    document = check_document_access(db, block.document_id, current_user.user_id)

    try:
        assert_document_editable(db, block.document_id)
        if not can_delete_block(db, block_id):
            raise HTTPException(status_code=400, detail="Block is not removable")

        from app.models.document.block_types import get_block_type_handler

        handler = get_block_type_handler(block.block_type_id)
        if handler:
            handler.on_delete(db, block_id, block.document_id)

        if not delete_block_or_bundle(db, block.document_id, block_id):
            raise HTTPException(status_code=404, detail="Block not found")
        mark_document_edited(db, document, current_user=current_user)
        regenerate_document_operations(db, block.document_id)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    notify_after_edit()


@router.post("/documents/{document_id}/commit", response_model=CommitResponse)
def commit_changes(
    document_id: int,
    commit_req: CommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = check_document_access(db, document_id, current_user.user_id)
    try:
        assert_document_editable(db, document_id)
        success, message = commit_operations(
            db=db,
            document_id=document_id,
            ops=commit_req.ops,
        )
        if not success:
            db.rollback()
            raise HTTPException(status_code=400, detail=message)
        mark_document_edited(db, document, current_user=current_user)
        db.commit()
    except WorkflowCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    notify_after_edit()
    return CommitResponse(success=True, message=message)

"""Service for block type handlers and system block lifecycle."""

import uuid
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.block_types import get_block_type_handler, get_system_block_handlers
from app.services.block_service import create_block


def initialize_system_blocks(db: Session, document_id: int) -> List[Block]:
    system_handlers = get_system_block_handlers()
    created_blocks: List[Block] = []

    sorted_handlers = sorted(
        system_handlers.items(),
        key=lambda item: item[1].fixed_position if item[1].fixed_position is not None else 9999,
    )

    previous_block_id = None
    for block_type_name, handler in sorted_handlers:
        block = create_block(
            db=db,
            document_id=document_id,
            block_type_id=block_type_name,
            props=handler.get_default_props(),
            previous_block_id=previous_block_id,
            is_system=True,
            is_removable=handler.is_removable,
            fixed_position=handler.fixed_position,
        )
        db.flush()
        handler.on_create(db, block.block_id, document_id, block.props)
        created_blocks.append(block)
        previous_block_id = block.block_id

    return created_blocks


def validate_block_constraints(db: Session, document_id: int, block_type_id: str) -> bool:
    handler = get_block_type_handler(block_type_id)
    if not handler:
        return True

    if not handler.allow_multiple_instances:
        count = db.execute(
            select(func.count(Block.block_id)).filter(
                Block.document_id == document_id,
                Block.block_type_id == block_type_id,
            )
        ).scalar()
        if count and count > 0:
            return False

    return True


def can_delete_block(db: Session, block_id: uuid.UUID) -> bool:
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        return False
    if block.is_system and not block.is_removable:
        return False
    return True


def can_reorder_block(db: Session, block_id: uuid.UUID) -> bool:
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        return False
    if block.fixed_position is not None:
        return False
    return True


def enrich_block_data_for_frontend(db: Session, block: Block) -> dict:
    handler = get_block_type_handler(block.block_type_id)
    if not handler:
        return {
            "block_id": str(block.block_id),
            "document_id": block.document_id,
            "previous_block_id": str(block.previous_block_id) if block.previous_block_id else None,
            "next_block_id": str(block.next_block_id) if block.next_block_id else None,
            "block_type_id": block.block_type_id,
            "props": block.props,
            "created_at": block.created_at,
            "updated_at": block.updated_at,
            "is_system": block.is_system,
            "is_removable": block.is_removable,
            "fixed_position": block.fixed_position,
            "field_limits": None,
        }

    enriched_props = handler.serialize_for_frontend(db, block.block_id, block.document_id, block.props)
    return {
        "block_id": str(block.block_id),
        "document_id": block.document_id,
        "previous_block_id": str(block.previous_block_id) if block.previous_block_id else None,
        "next_block_id": str(block.next_block_id) if block.next_block_id else None,
        "block_type_id": block.block_type_id,
        "props": enriched_props,
        "created_at": block.created_at,
        "updated_at": block.updated_at,
        "is_system": block.is_system,
        "is_removable": block.is_removable,
        "fixed_position": block.fixed_position,
        "editable_fields": handler.get_editable_fields(),
        "field_limits": handler.get_field_limits(),
    }

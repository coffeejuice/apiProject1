"""Service for managing block types and system blocks"""
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from app.models.document.block import Block, BlockType
from app.models.document.block_types import get_system_block_handlers, get_block_type_handler


def initialize_system_blocks(db: Session, document_id: int) -> List[Block]:
    """
    Create all required system blocks for a new document.
    Returns list of created blocks.
    """
    system_handlers = get_system_block_handlers()
    created_blocks = []

    # Sort by fixed_position to create in correct order
    sorted_handlers = sorted(
        system_handlers.items(),
        key=lambda x: x[1].fixed_position if x[1].fixed_position is not None else 9999
    )

    for block_type_name, handler in sorted_handlers:
        # Generate order key based on fixed position
        order_key = generate_order_key(handler.fixed_position)

        # Create block
        block = Block(
            block_id=uuid.uuid4(),
            document_id=document_id,
            parent_block_id=None,
            order_key=order_key,
            block_type=BlockType[block_type_name],
            text="",
            props=handler.get_default_props(),
            is_system=True,
            is_removable=handler.is_removable,
            fixed_position=handler.fixed_position
        )

        db.add(block)
        db.flush()  # Ensure block_id is available

        # Call handler's on_create hook
        handler.on_create(db, block.block_id, document_id, block.props)

        created_blocks.append(block)

    return created_blocks


def validate_block_constraints(db: Session, document_id: int, block_type: BlockType) -> bool:
    """
    Validate that creating/modifying a block doesn't violate constraints.
    Returns True if valid, False otherwise.
    """
    handler = get_block_type_handler(block_type.value)
    if not handler:
        return True  # Unknown block type, allow for now

    # Check if multiple instances are allowed
    if not handler.allow_multiple_instances:
        from sqlalchemy import select, func
        count = db.execute(
            select(func.count(Block.block_id)).filter(
                Block.document_id == document_id,
                Block.block_type == block_type
            )
        ).scalar()

        if count is not None and count > 0:
            return False  # Block already exists

    return True


def can_delete_block(db: Session, block_id: uuid.UUID) -> bool:
    """
    Check if a block can be deleted.
    Returns False if block is non-removable.
    """
    from sqlalchemy import select
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()

    if not block:
        return False

    # System blocks that are non-removable cannot be deleted
    if block.is_system and not block.is_removable:
        return False

    return True


def can_reorder_block(db: Session, block_id: uuid.UUID, new_order_key: str) -> bool:
    """
    Check if a block can be reordered.
    Returns False if block has a fixed position.
    """
    from sqlalchemy import select
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()

    if not block:
        return False

    # Blocks with fixed_position cannot be reordered
    if block.fixed_position is not None:
        return False

    return True


def generate_order_key(position: Optional[int]) -> str:
    """
    Generate order key for a fixed position.
    Uses position as prefix to ensure correct ordering.
    """
    import time
    import random

    # For fixed positions, use position * 1000000000000000000 as base
    # This ensures system blocks always come first
    if position is not None:
        timestamp = position * 1000000000000000000
    else:
        timestamp = int(time.time() * 1000000)

    suffix = random.randint(1000, 9999)
    return f"{timestamp:020d}-{suffix}"


def enrich_block_data_for_frontend(db: Session, block: Block) -> dict:
    """
    Enrich block data with handler-specific information for frontend.
    """
    handler = get_block_type_handler(block.block_type.value)
    if not handler:
        # No handler, return basic data
        return {
            "block_id": str(block.block_id),
            "block_type": block.block_type.value,
            "text": block.text,
            "props": block.props,
            "order_key": block.order_key,
            "is_system": block.is_system,
            "is_removable": block.is_removable,
            "fixed_position": block.fixed_position,
        }

    # Get enriched data from handler
    enriched_props = handler.serialize_for_frontend(
        db, block.block_id, block.document_id, block.props
    )

    return {
        "block_id": str(block.block_id),
        "block_type": block.block_type.value,
        "text": block.text,
        "props": enriched_props,
        "order_key": block.order_key,
        "is_system": block.is_system,
        "is_removable": block.is_removable,
        "fixed_position": block.fixed_position,
        "editable_fields": handler.get_editable_fields(),
    }

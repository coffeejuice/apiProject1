from typing import List, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.block_types import get_block_type_handler
from app.schemas import OperationPayload
from app.services.block_service import create_block_or_bundle, delete_block_or_bundle, move_block_after, update_block_props
from app.services.block_type_service import (
    can_delete_block,
    can_place_block_after,
    can_reorder_block,
    validate_block_constraints,
)
from app.services.operation_blocks import (
    build_default_operation_props,
    is_operation_block_type,
    sanitize_operation_props,
)


def apply_operations(
    db: Session,
    document_id: int,
    ops: List[OperationPayload],
) -> None:
    for op in ops:
        op_type = op.op_type
        data = op.data

        if op_type == "insert_block":
            block_type_id = str(data["block_type_id"])
            if not validate_block_constraints(db, document_id, block_type_id):
                raise ValueError(f"Cannot create block of type {block_type_id}: constraints violated")

            previous_block_id = data.get("previous_block_id")
            parsed_prev = UUID(previous_block_id) if previous_block_id else None
            if not can_place_block_after(db, document_id, parsed_prev):
                raise ValueError("Cannot insert before fixed system blocks")
            block_id = UUID(data["block_id"]) if data.get("block_id") else None

            create_block_or_bundle(
                db=db,
                document_id=document_id,
                block_type_id=block_type_id,
                props=(
                    build_default_operation_props(db, block_type_id, data.get("props", {}))
                    if is_operation_block_type(db, block_type_id)
                    else data.get("props", {})
                ),
                previous_block_id=parsed_prev,
                block_id=block_id,
            )

        elif op_type == "delete_block":
            block_id = UUID(str(data["block_id"]))
            if not can_delete_block(db, block_id):
                raise ValueError(f"Cannot delete block {block_id}: block is not removable")
            if not delete_block_or_bundle(db, document_id, block_id):
                raise ValueError(f"Block {block_id} not found")

        elif op_type == "move_block":
            block_id = UUID(str(data["block_id"]))
            if not can_reorder_block(db, block_id):
                raise ValueError(f"Cannot reorder block {block_id}: block has fixed position")
            previous_block_id = data.get("previous_block_id")
            parsed_prev = UUID(str(previous_block_id)) if previous_block_id else None
            if not can_place_block_after(db, document_id, parsed_prev):
                raise ValueError("Cannot move before fixed system blocks")
            moved = move_block_after(db, document_id, block_id, parsed_prev)
            if not moved:
                raise ValueError(f"Block {block_id} not found")

        elif op_type == "update_props":
            block_id = UUID(str(data["block_id"]))
            existing_block = db.execute(select(Block).filter(Block.block_id == block_id)).scalars().first()
            if not existing_block:
                raise ValueError(f"Block {block_id} not found")
            props = (
                sanitize_operation_props(db, existing_block.block_type_id, data.get("props", {}))
                if is_operation_block_type(db, existing_block.block_type_id)
                else data.get("props", {})
            )
            block = update_block_props(db, block_id, props)
            if not block:
                raise ValueError(f"Block {block_id} not found")

            handler = get_block_type_handler(block.block_type_id)
            if handler:
                handler.on_update(db, block.block_id, block.document_id, block.props)

        else:
            raise ValueError(f"Unsupported operation type: {op_type}")


def commit_operations(
    db: Session,
    document_id: int,
    ops: List[OperationPayload],
) -> Tuple[bool, str]:
    try:
        apply_operations(db, document_id, ops)
        return True, "Operations applied"
    except Exception as exc:
        return False, str(exc)

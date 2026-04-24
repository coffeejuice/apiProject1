"""Service for block type handlers and system block lifecycle."""

import uuid
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.block_types import get_block_type_handler, get_system_block_handlers
from app.services.block_service import create_block
from app.services.operation_blocks import (
    DEFORMATION_BUNDLE_LEADER_TYPE_ID,
    DEFORMATION_BUNDLE_MEMBER_TYPE_IDS,
    build_default_operation_props,
    get_operation_field_limits,
    is_insertable_operation_block_type,
    serialize_operation_block_for_frontend,
)


FIXED_MATERIAL_BLOCK_TYPE_ID = "5"
FIXED_MESH_BLOCK_TYPE_ID = "84"
FIXED_SYSTEM_BLOCK_ORDER = (
    "document_heading",
)
DEFORMATION_BUNDLE_TYPE_IDS = {
    *(str(type_id) for type_id in DEFORMATION_BUNDLE_MEMBER_TYPE_IDS),
}
DEFORMATION_BUNDLE_INSERT_BLOCKED_AFTER_TYPE_IDS: set[str] = set()


def _get_default_material_id_for_document(db: Session, document_id: int) -> int | None:
    from app.models.document.document import Document
    from app.models.library.material import MaterialVersion
    from app.models.project import Project

    document = db.get(Document, document_id)
    if document is None:
        return None

    if document.material_version_id is not None:
        material_version = db.get(MaterialVersion, document.material_version_id)
        if material_version is not None:
            return material_version.material_id

    project = db.get(Project, document.project_id)
    return project.material_id if project is not None else None


def _get_fixed_operation_default_props(db: Session, document_id: int, block_type_id: str) -> dict:
    if block_type_id == FIXED_MATERIAL_BLOCK_TYPE_ID:
        material_id = _get_default_material_id_for_document(db, document_id)
        return build_default_operation_props(
            db,
            block_type_id,
            {"material_id": material_id if material_id is not None else ""},
        )

    if block_type_id == FIXED_MESH_BLOCK_TYPE_ID:
        return build_default_operation_props(db, block_type_id, {"mesh_elements": 10})

    return build_default_operation_props(db, block_type_id)


def initialize_system_blocks(db: Session, document_id: int) -> List[Block]:
    system_handlers = get_system_block_handlers()
    created_blocks: List[Block] = []

    previous_block_id = None
    for fixed_position, block_type_name in enumerate(FIXED_SYSTEM_BLOCK_ORDER):
        handler = system_handlers.get(block_type_name)
        props = (
            handler.get_default_props()
            if handler is not None
            else _get_fixed_operation_default_props(db, document_id, block_type_name)
        )
        if block_type_name == "document_heading":
            material_id = _get_default_material_id_for_document(db, document_id)
            props = {
                **props,
                "material_id": material_id if material_id is not None else "",
                "mesh_elements": 10,
            }
        block = create_block(
            db=db,
            document_id=document_id,
            block_type_id=block_type_name,
            props=props,
            previous_block_id=previous_block_id,
            is_system=True,
            is_removable=False,
            fixed_position=fixed_position,
        )
        db.flush()
        if handler is not None:
            handler.on_create(db, block.block_id, document_id, block.props)
        created_blocks.append(block)
        previous_block_id = block.block_id

    return created_blocks


def validate_block_constraints(db: Session, document_id: int, block_type_id: str) -> bool:
    handler = get_block_type_handler(block_type_id)
    if not handler:
        return is_insertable_operation_block_type(db, block_type_id)

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


def can_place_block_after(db: Session, document_id: int, previous_block_id: uuid.UUID | None) -> bool:
    from app.models.document.document import Document

    document = db.get(Document, document_id)
    if document is None:
        return False

    if previous_block_id is None:
        if document.first_block_id is None:
            return True
        first_block = db.get(Block, document.first_block_id)
        return first_block is None or first_block.fixed_position is None

    previous_block = db.execute(
        select(Block).filter(
            Block.document_id == document_id,
            Block.block_id == previous_block_id,
        )
    ).scalars().first()
    if previous_block is None:
        return False

    if previous_block.block_type_id in DEFORMATION_BUNDLE_INSERT_BLOCKED_AFTER_TYPE_IDS:
        return False

    if previous_block.next_block_id is None:
        return True

    next_block = db.execute(
        select(Block).filter(
            Block.document_id == document_id,
            Block.block_id == previous_block.next_block_id,
        )
    ).scalars().first()
    return next_block is None or next_block.fixed_position is None


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
    if block.block_type_id in DEFORMATION_BUNDLE_TYPE_IDS:
        return False
    return True


def enrich_block_data_for_frontend(db: Session, block: Block) -> dict:
    handler = get_block_type_handler(block.block_type_id)
    if not handler:
        operation_props = serialize_operation_block_for_frontend(db, block.block_type_id, block.props)
        field_limits = get_operation_field_limits(db, block.block_type_id)
        operation_type = operation_props.get("operation_type")
        editable_fields = (
            operation_type.get("db_column_names")
            if isinstance(operation_type, dict)
            else None
        )
        return {
            "block_id": str(block.block_id),
            "document_id": block.document_id,
            "previous_block_id": str(block.previous_block_id) if block.previous_block_id else None,
            "next_block_id": str(block.next_block_id) if block.next_block_id else None,
            "block_type_id": block.block_type_id,
            "props": operation_props,
            "created_at": block.created_at,
            "updated_at": block.updated_at,
            "is_system": block.is_system,
            "is_removable": block.is_removable,
            "fixed_position": block.fixed_position,
            "editable_fields": editable_fields,
            "field_limits": field_limits,
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

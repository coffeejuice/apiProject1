"""Service for block type handlers and system block lifecycle."""

import uuid
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.block_types import get_block_type_handler, get_system_block_handlers
from app.services.block_service import (
    DEFORMATION_BLOCK_TYPE_ID,
    DOCUMENT_BLOCK_TYPE_ID,
    FURNACE_BLOCK_TYPE_ID,
    HEATING_BLOCK_TYPE_ID,
    OPERATION_BLOCK_TYPE_ID,
    SECTION_BLOCK_TYPE_IDS,
    create_block,
    create_block_or_bundle,
    get_ordered_blocks,
)
from app.services.block_props import (
    DOCUMENT_PROPERTIES,
    FURNACE_PROPERTIES,
    HEATING_PROPERTIES,
    normalize_deformation_block_props,
    normalize_furnace_block_props,
    normalize_heating_block_props,
)
from app.services.operation_blocks import (
    get_operation_field_limits,
    is_insertable_operation_block_type,
    is_operation_block_type,
    serialize_operation_block_for_frontend,
)


FIXED_SYSTEM_BLOCK_ORDER = (
    DOCUMENT_BLOCK_TYPE_ID,
)
USER_INSERTABLE_BLOCK_TYPES = {
    HEATING_BLOCK_TYPE_ID,
    FURNACE_BLOCK_TYPE_ID,
    DEFORMATION_BLOCK_TYPE_ID,
    OPERATION_BLOCK_TYPE_ID,
}


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


def initialize_system_blocks(db: Session, document_id: int) -> List[Block]:
    system_handlers = get_system_block_handlers()
    created_blocks: List[Block] = []

    previous_block_id = None
    for fixed_position, block_type_name in enumerate(FIXED_SYSTEM_BLOCK_ORDER):
        handler = system_handlers.get(block_type_name)
        props = (
            handler.get_default_props()
            if handler is not None
            else {}
        )
        if block_type_name == DOCUMENT_BLOCK_TYPE_ID:
            material_id = _get_default_material_id_for_document(db, document_id)
            document_properties = dict(props.get(DOCUMENT_PROPERTIES) or {})
            document_properties.update(
                {
                    "material_id": material_id if material_id is not None else "",
                    "mesh_elements": 10,
                    "section_numbering_start": 2,
                }
            )
            props = {
                **props,
                DOCUMENT_PROPERTIES: document_properties,
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

    deformation = create_block_or_bundle(
        db=db,
        document_id=document_id,
        block_type_id=DEFORMATION_BLOCK_TYPE_ID,
        props={},
        previous_block_id=previous_block_id,
    )
    created_blocks.append(deformation)
    return created_blocks


def validate_block_constraints(db: Session, document_id: int, block_type_id: str) -> bool:
    if block_type_id not in {DOCUMENT_BLOCK_TYPE_ID, *USER_INSERTABLE_BLOCK_TYPES}:
        return False

    handler = get_block_type_handler(block_type_id)
    if not handler:
        return block_type_id in USER_INSERTABLE_BLOCK_TYPES and (
            block_type_id != OPERATION_BLOCK_TYPE_ID or is_insertable_operation_block_type(db, block_type_id)
        )

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

    if previous_block.next_block_id is None:
        return True

    next_block = db.execute(
        select(Block).filter(
            Block.document_id == document_id,
            Block.block_id == previous_block.next_block_id,
        )
    ).scalars().first()
    return next_block is None or next_block.fixed_position is None


def _previous_ordered_block(blocks: list[Block], block: Block) -> Block | None:
    for index, candidate in enumerate(blocks):
        if candidate.block_id == block.block_id:
            return blocks[index - 1] if index > 0 else None
    return None


def _next_ordered_block(blocks: list[Block], block: Block) -> Block | None:
    for index, candidate in enumerate(blocks):
        if candidate.block_id == block.block_id:
            return blocks[index + 1] if index + 1 < len(blocks) else None
    return None


def _is_inside_deformation(db: Session, document_id: int, block: Block) -> bool:
    if block.block_type_id == DEFORMATION_BLOCK_TYPE_ID:
        return True
    if block.block_type_id in SECTION_BLOCK_TYPE_IDS:
        return False

    blocks = get_ordered_blocks(db, document_id)
    current = block
    while True:
        previous = _previous_ordered_block(blocks, current)
        if previous is None:
            return False
        if previous.block_type_id == DEFORMATION_BLOCK_TYPE_ID:
            return True
        if previous.block_type_id in SECTION_BLOCK_TYPE_IDS:
            return False
        current = previous


def _is_inside_heating(db: Session, document_id: int, block: Block) -> bool:
    if block.block_type_id == HEATING_BLOCK_TYPE_ID:
        return True
    if block.block_type_id in SECTION_BLOCK_TYPE_IDS:
        return False

    blocks = get_ordered_blocks(db, document_id)
    current = block
    while True:
        previous = _previous_ordered_block(blocks, current)
        if previous is None:
            return False
        if previous.block_type_id == HEATING_BLOCK_TYPE_ID:
            return True
        if previous.block_type_id in SECTION_BLOCK_TYPE_IDS:
            return False
        current = previous


def _is_valid_section_anchor(db: Session, document_id: int, previous_block: Block | None) -> bool:
    if previous_block is None:
        return False
    if previous_block.block_type_id == DOCUMENT_BLOCK_TYPE_ID:
        return True

    blocks = get_ordered_blocks(db, document_id)
    if previous_block.block_type_id in {HEATING_BLOCK_TYPE_ID, DEFORMATION_BLOCK_TYPE_ID}:
        next_block = _next_ordered_block(blocks, previous_block)
        return next_block is None or next_block.block_type_id in SECTION_BLOCK_TYPE_IDS

    if previous_block.block_type_id not in {FURNACE_BLOCK_TYPE_ID, OPERATION_BLOCK_TYPE_ID}:
        return False

    next_block = _next_ordered_block(blocks, previous_block)
    return next_block is None or next_block.block_type_id in SECTION_BLOCK_TYPE_IDS


def _count_operations_in_section(db: Session, document_id: int, operation_block: Block) -> int:
    blocks = get_ordered_blocks(db, document_id)
    try:
        operation_index = next(
            index for index, block in enumerate(blocks) if block.block_id == operation_block.block_id
        )
    except StopIteration:
        return 0

    section_start = operation_index
    while section_start >= 0 and blocks[section_start].block_type_id != DEFORMATION_BLOCK_TYPE_ID:
        if blocks[section_start].block_type_id in SECTION_BLOCK_TYPE_IDS:
            return 0
        section_start -= 1

    if section_start < 0:
        return 0

    count = 0
    for block in blocks[section_start + 1:]:
        if block.block_type_id in SECTION_BLOCK_TYPE_IDS:
            break
        if block.block_type_id == OPERATION_BLOCK_TYPE_ID:
            count += 1
    return count


def can_insert_block_after(
    db: Session,
    document_id: int,
    block_type_id: str,
    previous_block_id: uuid.UUID | None,
) -> bool:
    if not can_place_block_after(db, document_id, previous_block_id):
        return False
    previous_block = db.get(Block, previous_block_id) if previous_block_id else None
    if block_type_id == OPERATION_BLOCK_TYPE_ID:
        return previous_block is not None and _is_inside_deformation(db, document_id, previous_block)
    if block_type_id == FURNACE_BLOCK_TYPE_ID:
        return previous_block is not None and _is_inside_heating(db, document_id, previous_block)
    if block_type_id in {HEATING_BLOCK_TYPE_ID, DEFORMATION_BLOCK_TYPE_ID}:
        return _is_valid_section_anchor(db, document_id, previous_block)
    return True


def can_delete_block(db: Session, block_id: uuid.UUID) -> bool:
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        return False
    if block.is_system and not block.is_removable:
        return False
    if block.block_type_id == DEFORMATION_BLOCK_TYPE_ID:
        deformation_count = db.execute(
            select(func.count(Block.block_id)).where(
                Block.document_id == block.document_id,
                Block.block_type_id == DEFORMATION_BLOCK_TYPE_ID,
            )
        ).scalar()
        return bool(deformation_count and deformation_count > 1)
    if block.block_type_id == OPERATION_BLOCK_TYPE_ID:
        return _count_operations_in_section(db, block.document_id, block) > 1
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
        if block.block_type_id == HEATING_BLOCK_TYPE_ID:
            normalized = normalize_heating_block_props(block.props)
            heating_properties = dict(normalized.get(HEATING_PROPERTIES) or {})
            props = {
                "title": "Heating",
                **normalized,
                **heating_properties,
            }
            editable_fields = ["heating_properties"]
            field_limits = {"furnace_class_id": 255, "temperature": 255}
        elif block.block_type_id == FURNACE_BLOCK_TYPE_ID:
            normalized = normalize_furnace_block_props(block.props)
            furnace_properties = dict(normalized.get(FURNACE_PROPERTIES) or {})
            props = {
                "title": "Furnace",
                **normalized,
                **furnace_properties,
            }
            editable_fields = ["furnace_properties"]
            field_limits = {"furnace_class_id": 255, "temperature": 255}
        elif block.block_type_id == DEFORMATION_BLOCK_TYPE_ID:
            normalized = normalize_deformation_block_props(block.props)
            props = {"title": "Deformation", **normalized}
            editable_fields = []
            field_limits = {}
        elif is_operation_block_type(db, block.block_type_id):
            props = serialize_operation_block_for_frontend(db, block.block_type_id, block.props)
            editable_fields = ["operation_template_id", "target"]
            field_limits = get_operation_field_limits(db, block.block_type_id)
        else:
            props = dict(block.props or {})
            editable_fields = []
            field_limits = {}
        return {
            "block_id": str(block.block_id),
            "document_id": block.document_id,
            "previous_block_id": str(block.previous_block_id) if block.previous_block_id else None,
            "next_block_id": str(block.next_block_id) if block.next_block_id else None,
            "block_type_id": block.block_type_id,
            "props": props,
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

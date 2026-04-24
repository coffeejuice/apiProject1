from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.document import Document
from app.services.operation_blocks import build_default_operation_props


DEFORMATION_BUNDLE_TYPE_ORDER = ("24",)
DEFORMATION_BUNDLE_TYPE_SET = set(DEFORMATION_BUNDLE_TYPE_ORDER)


def _get_document_or_none(db: Session, document_id: int) -> Optional[Document]:
    return db.execute(
        select(Document).filter(Document.document_id == document_id)
    ).scalars().first()


def get_ordered_blocks(db: Session, document_id: int) -> List[Block]:
    document = _get_document_or_none(db, document_id)
    if not document or not document.first_block_id:
        return []

    blocks_by_id = {
        block.block_id: block
        for block in db.execute(
            select(Block).filter(Block.document_id == document_id)
        ).scalars().all()
    }

    ordered: List[Block] = []
    current_id = document.first_block_id
    visited: set[UUID] = set()

    while current_id and current_id not in visited:
        visited.add(current_id)
        block = blocks_by_id.get(current_id)
        if not block:
            break
        ordered.append(block)
        current_id = block.next_block_id

    return ordered


def get_root_blocks(db: Session, document_id: int) -> List[Block]:
    return get_ordered_blocks(db, document_id)


def create_block(
    db: Session,
    document_id: int,
    block_type_id: str,
    props: dict,
    previous_block_id: Optional[UUID] = None,
    block_id: Optional[UUID] = None,
    *,
    is_system: bool = False,
    is_removable: bool = True,
    fixed_position: Optional[int] = None,
) -> Block:
    document = _get_document_or_none(db, document_id)
    if not document:
        raise ValueError("Document not found")

    if block_id is None:
        block_id = uuid4()

    new_block = Block(
        block_id=block_id,
        document_id=document_id,
        previous_block_id=None,
        next_block_id=None,
        block_type_id=block_type_id,
        props=props or {},
        is_system=is_system,
        is_removable=is_removable,
        fixed_position=fixed_position,
    )
    db.add(new_block)
    db.flush()

    # Insert at head
    if previous_block_id is None:
        old_head_id = document.first_block_id
        new_block.previous_block_id = None
        new_block.next_block_id = old_head_id
        document.first_block_id = new_block.block_id

        if old_head_id:
            old_head = db.execute(
                select(Block).filter(
                    Block.block_id == old_head_id,
                    Block.document_id == document_id,
                )
            ).scalars().first()
            if old_head:
                old_head.previous_block_id = new_block.block_id
        return new_block

    # Insert after a specific block
    prev_block = db.execute(
        select(Block).filter(
            Block.block_id == previous_block_id,
            Block.document_id == document_id,
        )
    ).scalars().first()
    if not prev_block:
        raise ValueError("previous_block_id not found in document")

    next_block_id = prev_block.next_block_id
    new_block.previous_block_id = prev_block.block_id
    new_block.next_block_id = next_block_id
    prev_block.next_block_id = new_block.block_id

    if next_block_id:
        next_block = db.execute(
            select(Block).filter(
                Block.block_id == next_block_id,
                Block.document_id == document_id,
            )
        ).scalars().first()
        if next_block:
            next_block.previous_block_id = new_block.block_id

    return new_block


def create_block_or_bundle(
    db: Session,
    document_id: int,
    block_type_id: str,
    props: dict,
    previous_block_id: Optional[UUID] = None,
    block_id: Optional[UUID] = None,
) -> Block:
    if str(block_type_id) != DEFORMATION_BUNDLE_TYPE_ORDER[0]:
        return create_block(
            db=db,
            document_id=document_id,
            block_type_id=block_type_id,
            props=props,
            previous_block_id=previous_block_id,
            block_id=block_id,
        )

    leader = create_block(
        db=db,
        document_id=document_id,
        block_type_id=DEFORMATION_BUNDLE_TYPE_ORDER[0],
        props=build_default_operation_props(db, DEFORMATION_BUNDLE_TYPE_ORDER[0], props),
        previous_block_id=previous_block_id,
        block_id=block_id,
    )
    previous_id = leader.block_id
    for member_type_id in DEFORMATION_BUNDLE_TYPE_ORDER[1:]:
        member_props = build_default_operation_props(db, member_type_id, props)
        member = create_block(
            db=db,
            document_id=document_id,
            block_type_id=member_type_id,
            props=member_props,
            previous_block_id=previous_id,
        )
        previous_id = member.block_id

    return leader


def move_block_after(
    db: Session,
    document_id: int,
    block_id: UUID,
    previous_block_id: Optional[UUID],
) -> Optional[Block]:
    document = _get_document_or_none(db, document_id)
    if not document:
        return None

    block = db.execute(
        select(Block).filter(
            Block.block_id == block_id,
            Block.document_id == document_id,
        )
    ).scalars().first()
    if not block:
        return None

    if previous_block_id == block.block_id:
        raise ValueError("Block cannot reference itself as previous")

    # No-op if already in requested position
    if block.previous_block_id == previous_block_id:
        return block

    # Detach from current position
    prev_block = None
    next_block = None
    if block.previous_block_id:
        prev_block = db.execute(
            select(Block).filter(
                Block.block_id == block.previous_block_id,
                Block.document_id == document_id,
            )
        ).scalars().first()
    if block.next_block_id:
        next_block = db.execute(
            select(Block).filter(
                Block.block_id == block.next_block_id,
                Block.document_id == document_id,
            )
        ).scalars().first()

    if prev_block:
        prev_block.next_block_id = block.next_block_id
    else:
        document.first_block_id = block.next_block_id

    if next_block:
        next_block.previous_block_id = block.previous_block_id

    # Insert at head
    if previous_block_id is None:
        old_head_id = document.first_block_id
        block.previous_block_id = None
        block.next_block_id = old_head_id
        document.first_block_id = block.block_id

        if old_head_id and old_head_id != block.block_id:
            old_head = db.execute(
                select(Block).filter(
                    Block.block_id == old_head_id,
                    Block.document_id == document_id,
                )
            ).scalars().first()
            if old_head:
                old_head.previous_block_id = block.block_id
        return block

    # Insert after target previous block
    target_prev = db.execute(
        select(Block).filter(
            Block.block_id == previous_block_id,
            Block.document_id == document_id,
        )
    ).scalars().first()
    if not target_prev:
        raise ValueError("Target previous block not found")

    target_next_id = target_prev.next_block_id
    target_prev.next_block_id = block.block_id
    block.previous_block_id = target_prev.block_id
    block.next_block_id = target_next_id

    if target_next_id:
        target_next = db.execute(
            select(Block).filter(
                Block.block_id == target_next_id,
                Block.document_id == document_id,
            )
        ).scalars().first()
        if target_next:
            target_next.previous_block_id = block.block_id

    return block


def update_block_props(
    db: Session,
    block_id: UUID,
    props: dict,
) -> Optional[Block]:
    block = db.execute(
        select(Block).filter(Block.block_id == block_id)
    ).scalars().first()
    if not block:
        return None
    block.props = props or {}
    return block


def delete_block(db: Session, document_id: int, block_id: UUID) -> bool:
    document = _get_document_or_none(db, document_id)
    if not document:
        return False

    block = db.execute(
        select(Block).filter(
            Block.block_id == block_id,
            Block.document_id == document_id,
        )
    ).scalars().first()
    if not block:
        return False

    prev_block = None
    next_block = None
    if block.previous_block_id:
        prev_block = db.execute(
            select(Block).filter(
                Block.block_id == block.previous_block_id,
                Block.document_id == document_id,
            )
        ).scalars().first()
    if block.next_block_id:
        next_block = db.execute(
            select(Block).filter(
                Block.block_id == block.next_block_id,
                Block.document_id == document_id,
            )
        ).scalars().first()

    if prev_block:
        prev_block.next_block_id = block.next_block_id
    else:
        document.first_block_id = block.next_block_id

    if next_block:
        next_block.previous_block_id = block.previous_block_id

    db.delete(block)
    return True


def _get_block_by_id(db: Session, document_id: int, block_id: UUID | None) -> Block | None:
    if block_id is None:
        return None
    return db.execute(
        select(Block).filter(
            Block.block_id == block_id,
            Block.document_id == document_id,
        )
    ).scalars().first()


def _previous_block(db: Session, document_id: int, block: Block | None) -> Block | None:
    return _get_block_by_id(db, document_id, block.previous_block_id if block else None)


def _next_block(db: Session, document_id: int, block: Block | None) -> Block | None:
    return _get_block_by_id(db, document_id, block.next_block_id if block else None)


def get_deformation_bundle_blocks(db: Session, document_id: int, block_id: UUID) -> list[Block]:
    block = _get_block_by_id(db, document_id, block_id)
    if block is None or block.block_type_id not in DEFORMATION_BUNDLE_TYPE_SET:
        return []

    leader = block
    while leader.block_type_id != DEFORMATION_BUNDLE_TYPE_ORDER[0]:
        previous = _previous_block(db, document_id, leader)
        if previous is None or previous.block_type_id not in DEFORMATION_BUNDLE_TYPE_SET:
            return [block]
        leader = previous

    bundle = [leader]
    current = leader
    for expected_type_id in DEFORMATION_BUNDLE_TYPE_ORDER[1:]:
        current = _next_block(db, document_id, current)
        if current is None or current.block_type_id != expected_type_id:
            return [block]
        bundle.append(current)

    return bundle


def delete_block_or_bundle(db: Session, document_id: int, block_id: UUID) -> bool:
    bundle = get_deformation_bundle_blocks(db, document_id, block_id)
    if not bundle:
        return delete_block(db, document_id, block_id)

    deleted_any = False
    for block in bundle:
        deleted_any = delete_block(db, document_id, block.block_id) or deleted_any
    return deleted_any

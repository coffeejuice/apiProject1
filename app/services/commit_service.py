from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from app.models import Process, Block, Revision, LegacyOperation, OperationType, BlockType, RevisionSnapshot, Device
from app.schemas import OpData, ConflictInfo

def check_duplicate_commit(
    db: Session,
    device_id: UUID,
    client_batch_id: UUID
) -> Optional[Revision]:
    """Check if this commit was already applied (idempotency)"""
    return db.execute(select(Revision).filter(
        Revision.device_id == device_id,
        Revision.client_batch_id == client_batch_id
    )).scalars().first()

def detect_conflicts(
    db: Session,
    process_id: int,
    base_rev: int,
    ops: List[OpData]
) -> List[ConflictInfo]:
    """Detect conflicts between client ops and server state"""
    conflicts = []

    # Get ops since base_rev
    server_ops = db.execute(select(LegacyOperation).join(Revision).filter(
        Revision.process_id == process_id,
        Revision.rev_number > base_rev
    )).scalars().all()

    # Build map of server changes
    server_changes: Dict[UUID, List[LegacyOperation]] = {}
    for server_op in server_ops:
        block_id = server_op.block_id
        if block_id not in server_changes:
            server_changes[block_id] = []
        server_changes[block_id].append(server_op)

    # Check client ops against server changes
    for client_op in ops:
        block_id_str = client_op.data.get("block_id")
        if not block_id_str:
            continue
        block_id = UUID(block_id_str)
        if block_id not in server_changes:
            continue

        # Simple conflict detection: same block modified
        for server_op in server_changes[block_id]:
            if client_op.op_type == OperationType.update_text and server_op.op_type == OperationType.update_text:
                conflicts.append(ConflictInfo(
                    block_id=block_id,
                    field="text",
                    server_value=server_op.data.get("text"),
                    client_value=client_op.data.get("text")
                ))
            elif client_op.op_type == OperationType.update_props and server_op.op_type == OperationType.update_props:
                conflicts.append(ConflictInfo(
                    block_id=block_id,
                    field="props",
                    server_value=server_op.data.get("props"),
                    client_value=client_op.data.get("props")
                ))

    return conflicts

def apply_operations(
    db: Session,
    process_id: int,
    ops: List[OpData]
) -> None:
    """Apply operations to document blocks"""
    for op in ops:
        if op.op_type == OperationType.insert_block:
            block = Block(
                block_id=UUID(op.data["block_id"]),
                process_id=process_id,
                parent_block_id=UUID(op.data["parent_block_id"]) if op.data.get("parent_block_id") else None,
                order_key=op.data["order_key"],
                block_type=BlockType[op.data["block_type"]],
                text=op.data.get("text", ""),
                props=op.data.get("props", {})
            )
            db.add(block)

        elif op.op_type == OperationType.delete_block:
            block_obj = db.execute(select(Block).filter(Block.block_id == UUID(op.data["block_id"]))).scalars().first()
            if block_obj:
                db.delete(block_obj)

        elif op.op_type == OperationType.move_block:
            block_obj = db.execute(select(Block).filter(Block.block_id == UUID(op.data["block_id"]))).scalars().first()
            if block_obj:
                block_obj.parent_block_id = UUID(op.data["parent_block_id"]) if op.data.get("parent_block_id") else None
                block_obj.order_key = op.data["order_key"]

        elif op.op_type == OperationType.update_text:
            block_obj = db.execute(select(Block).filter(Block.block_id == UUID(op.data["block_id"]))).scalars().first()
            if block_obj:
                block_obj.text = op.data["text"]

        elif op.op_type == OperationType.update_props:
            block_obj = db.execute(select(Block).filter(Block.block_id == UUID(op.data["block_id"]))).scalars().first()
            if block_obj:
                block_obj.props = op.data["props"]

def commit_operations(
    db: Session,
    process_id: int,
    device_id: UUID,
    client_batch_id: UUID,
    base_rev_number: int,
    ops: List[OpData],
    user_id: int
) -> Tuple[bool, Optional[int], Optional[List[ConflictInfo]]]:
    """
    Commit operations to document.
    Returns (success, new_rev_number, conflicts)
    """

    # Check for duplicate commit
    existing = check_duplicate_commit(db, device_id, client_batch_id)
    if existing:
        return True, existing.rev_number, None

    # Ensure device exists (auto-register if not)
    device = db.execute(select(Device).filter(Device.device_id == device_id)).scalars().first()
    if not device:
        device = Device(
            device_id=device_id,
            user_id=user_id,
            device_name="Auto-registered device"
        )
        db.add(device)
        db.flush()

    # Get document
    doc = db.execute(select(Process).filter(Process.process_id == process_id)).scalars().first()
    if not doc:
        return False, None, None

    # Check conflicts
    if base_rev_number < doc.current_rev_number:
        conflicts = detect_conflicts(db, process_id, base_rev_number, ops)
        if conflicts:
            return False, None, conflicts

    # Apply operations
    try:
        apply_operations(db, process_id, ops)

        # Create new revision
        new_rev_number = doc.current_rev_number + 1
        revision = Revision(
            process_id=process_id,
            rev_number=new_rev_number,
            device_id=device_id,
            client_batch_id=client_batch_id,
            created_by=user_id
        )
        db.add(revision)
        db.flush()

        # Store operations
        for op in ops:
            operation = LegacyOperation(
                revision_id=revision.revision_id,
                op_type=op.op_type,
                block_id=UUID(op.data["block_id"]),
                data=op.data
            )
            db.add(operation)

        # Update document rev number
        doc.current_rev_number = new_rev_number

        db.commit()
        return True, new_rev_number, None

    except Exception as e:
        print(f"Error in commit_operations: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False, None, None

def create_snapshot(db: Session, revision_id: UUID) -> None:
    """Create a snapshot of all blocks for a revision"""
    revision = db.execute(select(Revision).filter(Revision.revision_id == revision_id)).scalars().first()
    if not revision:
        return

    blocks = db.execute(select(Block).filter(Block.process_id == revision.process_id)).scalars().all()
    blocks_data = [
        {
            "block_id": str(block.block_id),
            "parent_block_id": str(block.parent_block_id) if block.parent_block_id else None,
            "order_key": block.order_key,
            "block_type": block.block_type.value,
            "text": block.text,
            "props": block.props
        }
        for block in blocks
    ]

    snapshot = RevisionSnapshot(
        revision_id=revision_id,
        blocks_data=blocks_data
    )
    db.add(snapshot)
    db.commit()

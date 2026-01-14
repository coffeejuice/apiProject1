from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete
from typing import List
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.revision import Revision, Operation
from app.models.block import Block
from app.models.process import Process, Role
from app.schemas import RevisionResponse, RevisionListResponse, DiffResponse
from app.auth import get_current_user
from app.routers.process import check_process_access

router = APIRouter(prefix="/documents/{process_id}/revisions", tags=["revisions"])

@router.get("", response_model=RevisionListResponse)
def list_revisions(
    process_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_process_access(db, process_id, current_user.user_id)

    stmt = select(Revision).filter(Revision.process_id == process_id).order_by(Revision.rev_number.desc())
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    revisions = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    return RevisionListResponse(revisions=list(revisions), total=total)

@router.post("/{rev_number}/restore")
def restore_revision(
    process_id: int,
    rev_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_process_access(db, process_id, current_user.user_id, Role.editor)

    # Get target revision
    revision = db.execute(select(Revision).filter(
        Revision.process_id == process_id,
        Revision.rev_number == rev_number
    )).scalars().first()

    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    # Check if snapshot exists
    if revision.snapshot:
        # Restore from snapshot
        db.execute(delete(Block).filter(Block.process_id == process_id))

        for block_data in revision.snapshot.blocks_data:
            block = Block(
                block_id=UUID(block_data["block_id"]),
                process_id=process_id,
                parent_block_id=UUID(block_data["parent_block_id"]) if block_data["parent_block_id"] else None,
                order_key=block_data["order_key"],
                block_type=block_data["block_type"],
                text=block_data["text"],
                props=block_data["props"]
            )
            db.add(block)
    else:
        # Replay ops from revision 0 to target
        db.execute(delete(Block).filter(Block.process_id == process_id))

        revisions = db.execute(select(Revision).filter(
            Revision.process_id == process_id,
            Revision.rev_number <= rev_number
        ).order_by(Revision.rev_number)).scalars().all()

        for rev in revisions:
            ops = db.execute(select(Operation).filter(Operation.revision_id == rev.revision_id)).scalars().all()
            from app.services.commit_service import apply_operations
            from app.schemas import OpData
            op_data_list = [
                OpData(op_type=op.op_type, data=op.data)
                for op in ops
            ]
            apply_operations(db, process_id, op_data_list)

    # Update document revision
    doc = db.execute(select(Process).filter(Process.process_id == process_id)).scalars().first()
    if doc:
        doc.current_rev_number = rev_number

    db.commit()
    return {"message": "Process restored", "rev_number": rev_number}

@router.get("/diff", response_model=DiffResponse)
def get_diff(
    process_id: int,
    from_rev: int = Query(..., alias="from"),
    to_rev: int = Query(..., alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_process_access(db, process_id, current_user.user_id)

    # Get ops between revisions
    ops = db.execute(select(Operation).join(Revision).filter(
        Revision.process_id == process_id,
        Revision.rev_number > from_rev,
        Revision.rev_number <= to_rev
    ).order_by(Revision.rev_number)).scalars().all()

    changes = [
        {
            "op_type": op.op_type.value,
            "block_id": str(op.block_id),
            "data": op.data
        }
        for op in ops
    ]

    return DiffResponse(from_rev=from_rev, to_rev=to_rev, changes=changes)

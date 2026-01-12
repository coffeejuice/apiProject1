from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.database import get_db
from app.models import User, Revision, Operation, Block, Document, Role
from app.schemas import RevisionResponse, RevisionListResponse, DiffResponse
from app.auth import get_current_user
from app.routers.documents import check_document_access

router = APIRouter(prefix="/documents/{document_id}/revisions", tags=["revisions"])

@router.get("", response_model=RevisionListResponse)
def list_revisions(
    document_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id)

    query = db.query(Revision).filter(Revision.document_id == document_id).order_by(Revision.rev_number.desc())
    total = query.count()
    revisions = query.offset((page - 1) * page_size).limit(page_size).all()

    return RevisionListResponse(revisions=revisions, total=total)

@router.post("/{rev_number}/restore")
def restore_revision(
    document_id: UUID,
    rev_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id, Role.editor)

    # Get target revision
    revision = db.query(Revision).filter(
        Revision.document_id == document_id,
        Revision.rev_number == rev_number
    ).first()

    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    # Check if snapshot exists
    if revision.snapshot:
        # Restore from snapshot
        db.query(Block).filter(Block.document_id == document_id).delete()

        for block_data in revision.snapshot.blocks_data:
            block = Block(
                block_id=UUID(block_data["block_id"]),
                document_id=document_id,
                parent_block_id=UUID(block_data["parent_block_id"]) if block_data["parent_block_id"] else None,
                order_key=block_data["order_key"],
                block_type=block_data["block_type"],
                text=block_data["text"],
                props=block_data["props"]
            )
            db.add(block)
    else:
        # Replay ops from revision 0 to target
        db.query(Block).filter(Block.document_id == document_id).delete()

        revisions = db.query(Revision).filter(
            Revision.document_id == document_id,
            Revision.rev_number <= rev_number
        ).order_by(Revision.rev_number).all()

        for rev in revisions:
            ops = db.query(Operation).filter(Operation.revision_id == rev.revision_id).all()
            from app.services.commit_service import apply_operations
            from app.schemas import OpData
            op_data_list = [
                OpData(op_type=op.op_type, data=op.data)
                for op in ops
            ]
            apply_operations(db, document_id, op_data_list)

    # Update document revision
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    doc.current_rev_number = rev_number

    db.commit()
    return {"message": "Document restored", "rev_number": rev_number}

@router.get("/diff", response_model=DiffResponse)
def get_diff(
    document_id: UUID,
    from_rev: int = Query(..., alias="from"),
    to_rev: int = Query(..., alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_document_access(db, document_id, current_user.user_id)

    # Get ops between revisions
    ops = db.query(Operation).join(Revision).filter(
        Revision.document_id == document_id,
        Revision.rev_number > from_rev,
        Revision.rev_number <= to_rev
    ).order_by(Revision.rev_number).all()

    changes = [
        {
            "op_type": op.op_type.value,
            "block_id": str(op.block_id),
            "data": op.data
        }
        for op in ops
    ]

    return DiffResponse(from_rev=from_rev, to_rev=to_rev, changes=changes)

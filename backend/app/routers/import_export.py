from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import User, Process, Block, BlockType, Role
from app.schemas import ExportResponse, ImportRequest, ProcessResponse
from app.auth import get_current_user
from app.routers.process import check_process_access
from app.services.import_export_service import export_to_markdown, import_from_markdown

router = APIRouter(tags=["import-export"])

@router.get("/documents/{process_id}/export", response_model=ExportResponse)
def export_document(
    process_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    check_process_access(db, process_id, current_user.user_id)
    markdown = export_to_markdown(db, process_id)
    return ExportResponse(markdown=markdown)

@router.post("/documents/import", response_model=ProcessResponse)
def import_document(
    import_data: ImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Create new document
    doc = Process(
        user_id=current_user.user_id,
        title=import_data.title,
        material_id=1
    )
    db.add(doc)
    db.flush()

    # Parse markdown to blocks
    blocks_data = import_from_markdown(import_data.markdown)

    # Create blocks
    for block_data in blocks_data:
        block = Block(
            block_id=UUID(block_data["block_id"]),
            process_id=doc.process_id,
            parent_block_id=UUID(block_data["parent_block_id"]) if block_data.get("parent_block_id") else None,
            order_key=block_data["order_key"],
            block_type=BlockType[block_data["block_type"]],
            text=block_data.get("text", ""),
            props=block_data.get("props", {})
        )
        db.add(block)

    db.commit()
    db.refresh(doc)
    return doc

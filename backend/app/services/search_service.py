from typing import List, Optional
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.document import Document
from app.models.project import Project
from app.schemas import SearchResult


def search_blocks(
    db: Session,
    user_id: int,
    query: str,
    document_id: Optional[int] = None,
    limit: int = 50,
) -> List[SearchResult]:
    stmt = (
        select(Document)
        .join(Project, Project.project_id == Document.project_id)
        .filter(Project.user_id == user_id, Project.deleted_at.is_(None))
    )

    if document_id is not None:
        stmt = stmt.filter(Document.document_id == document_id)

    search_pattern = f"%{query}%"
    stmt = stmt.filter(
        or_(
            Document.name.ilike(search_pattern),
            Document.notes.ilike(search_pattern),
        )
    )
    stmt = stmt.filter(Document.deleted_at.is_(None))

    documents = db.execute(stmt.limit(limit)).scalars().all()

    results: List[SearchResult] = []
    for document in documents:
        first_block = db.execute(
            select(Block.block_id, Block.block_type_id)
            .filter(Block.document_id == document.document_id)
            .limit(1)
        ).first()

        if first_block:
            block_id, block_type_id = first_block
        else:
            block_id, block_type_id = uuid4(), "document_heading"

        snippet = document.name
        if document.notes:
            snippet = f"{document.name} - {document.notes[:120]}"

        results.append(
            SearchResult(
                block_id=block_id,
                document_id=document.document_id,
                snippet=snippet,
                block_type_id=block_type_id,
            )
        )
    return results

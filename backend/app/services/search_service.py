from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from typing import List, Optional
from uuid import UUID, uuid4
from app.models.document.block import Block, BlockType
from app.models.document.document import Document, DocumentACL, Role
from app.schemas import SearchResult

def search_blocks(
    db: Session,
    user_id: int,
    query: str,
    document_id: Optional[int] = None,
    limit: int = 50
) -> List[SearchResult]:
    """
    Search documents by title.
    Returns documents user has access to.
    """
    # Build base query - search by document title
    stmt = select(Document)

    # Filter by document if specified
    if document_id:
        stmt = stmt.filter(Document.document_id == document_id)

    # Filter by title search
    search_pattern = f"%{query}%"
    stmt = stmt.filter(Document.title.ilike(search_pattern))

    # Filter by access rights
    stmt = stmt.filter(
        or_(
            Document.user_id == user_id,
            Document.document_id.in_(
                select(DocumentACL.document_id).filter(
                    DocumentACL.user_id == user_id
                )
            )
        )
    )

    # Exclude deleted documents
    stmt = stmt.filter(Document.deleted_at == None)

    documents = db.execute(stmt.limit(limit)).scalars().all()

    # Create results with document titles as snippets
    results = []
    for document in documents:
        # Use title as snippet
        title = document.title or "Untitled"

        # Create a dummy block_id since we're searching documents not blocks
        # Use first block if exists, otherwise generate a UUID
        first_block = db.execute(
            select(Block.block_id).filter(Block.document_id == document.document_id).limit(1)
        ).scalar_one_or_none()

        block_id = first_block if first_block else uuid4()

        results.append(SearchResult(
            block_id=block_id,
            document_id=document.document_id,
            snippet=title,
            block_type=BlockType.paragraph
        ))

    return results

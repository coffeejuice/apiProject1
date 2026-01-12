from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from uuid import UUID
from app.models import Block, Document, DocumentACL, Role
from app.schemas import SearchResult

def search_blocks(
    db: Session,
    user_id: UUID,
    query: str,
    document_id: Optional[UUID] = None,
    limit: int = 50
) -> List[SearchResult]:
    """
    Search blocks by text content.
    Returns blocks user has access to.
    """
    # Build base query
    q = db.query(Block).join(Document)

    # Filter by document if specified
    if document_id:
        q = q.filter(Block.document_id == document_id)

    # Filter by text search
    search_pattern = f"%{query}%"
    q = q.filter(Block.text.ilike(search_pattern))

    # Filter by access rights
    q = q.filter(
        or_(
            Document.owner_id == user_id,
            Document.document_id.in_(
                db.query(DocumentACL.document_id).filter(
                    DocumentACL.user_id == user_id
                )
            )
        )
    )

    # Exclude deleted documents
    q = q.filter(Document.deleted_at == None)

    blocks = q.limit(limit).all()

    # Create results with snippets
    results = []
    for block in blocks:
        # Create snippet (50 chars before/after match)
        text = block.text
        idx = text.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 50)
            end = min(len(text), idx + len(query) + 50)
            snippet = text[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
        else:
            snippet = text[:100]

        results.append(SearchResult(
            block_id=block.block_id,
            document_id=block.document_id,
            snippet=snippet,
            block_type=block.block_type
        ))

    return results

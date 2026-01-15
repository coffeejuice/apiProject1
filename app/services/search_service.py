from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from typing import List, Optional
from uuid import UUID
from app.models.document.block import Block
from app.models.document.process import Process, ProcessACL, Role
from app.schemas import SearchResult

def search_blocks(
    db: Session,
    user_id: int,
    query: str,
    document_id: Optional[int] = None,
    limit: int = 50
) -> List[SearchResult]:
    """
    Search blocks by text content.
    Returns blocks user has access to.
    """
    # Build base query
    stmt = select(Block).join(Process)

    # Filter by document if specified
    if document_id:
        stmt = stmt.filter(Block.process_id == document_id)

    # Filter by text search
    search_pattern = f"%{query}%"
    stmt = stmt.filter(Block.text.ilike(search_pattern))

    # Filter by access rights
    stmt = stmt.filter(
        or_(
            Process.user_id == user_id,
            Process.process_id.in_(
                select(ProcessACL.process_id).filter(
                    ProcessACL.user_id == user_id
                )
            )
        )
    )

    # Exclude deleted documents
    stmt = stmt.filter(Process.deleted_at == None)

    blocks = db.execute(stmt.limit(limit)).scalars().all()

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
            process_id=block.process_id,
            snippet=snippet,
            block_type=block.block_type
        ))

    return results

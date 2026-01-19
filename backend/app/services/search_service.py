from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from typing import List, Optional
from uuid import UUID, uuid4
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
    Search documents by title.
    Returns documents user has access to.
    """
    # Build base query - search by document title
    stmt = select(Process)

    # Filter by document if specified
    if document_id:
        stmt = stmt.filter(Process.process_id == document_id)

    # Filter by title search
    search_pattern = f"%{query}%"
    stmt = stmt.filter(Process.title.ilike(search_pattern))

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

    processes = db.execute(stmt.limit(limit)).scalars().all()

    # Create results with document titles as snippets
    results = []
    for process in processes:
        # Use title as snippet
        title = process.title or "Untitled"

        # Create a dummy block_id since we're searching documents not blocks
        # Use first block if exists, otherwise generate a UUID
        first_block = db.execute(
            select(Block.block_id).filter(Block.process_id == process.process_id).limit(1)
        ).scalar_one_or_none()

        block_id = first_block if first_block else uuid4()

        results.append(SearchResult(
            block_id=block_id,
            process_id=process.process_id,
            snippet=title,
            block_type="paragraph"
        ))

    return results

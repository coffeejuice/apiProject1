from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.schemas import SearchResponse
from app.auth import get_current_user
from app.services.search_service import search_blocks

router = APIRouter(prefix="/search", tags=["search"])

@router.get("", response_model=SearchResponse)
def search_all(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search across all accessible documents"""
    results = search_blocks(db, current_user.user_id, q, limit=limit)
    return SearchResponse(results=results, total=len(results))

document_search_router = APIRouter(prefix="/documents/{process_id}/search", tags=["search"])

@document_search_router.get("", response_model=SearchResponse)
def search_document(
    process_id: int,
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search within a specific document"""
    from app.routers.process import check_process_access
    check_process_access(db, process_id, current_user.user_id)

    results = search_blocks(db, current_user.user_id, q, document_id=process_id, limit=limit)
    return SearchResponse(results=results, total=len(results))

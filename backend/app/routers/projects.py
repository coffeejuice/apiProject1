from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.models.document.document import Document
from app.schemas import (
    DocumentListResponse,
    DocumentResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def get_owned_project_or_404(db: Session, project_id: int, user_id: int) -> Project:
    project = db.execute(
        select(Project).filter(
            Project.project_id == project_id,
            Project.deleted_at.is_(None),
        )
    ).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(
        user_id=current_user.user_id,
        material_id=payload.material_id,
        name=payload.name,
        notes=payload.notes,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Project).filter(
        Project.user_id == current_user.user_id,
        Project.deleted_at.is_(None),
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    projects = db.execute(
        stmt.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(project) for project in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_owned_project_or_404(db, project_id, current_user.user_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_owned_project_or_404(db, project_id, current_user.user_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(project, key, value)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_owned_project_or_404(db, project_id, current_user.user_id)
    project.deleted_at = datetime.utcnow()
    db.commit()


@router.get("/{project_id}/documents", response_model=DocumentListResponse)
def list_project_documents(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_deleted: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_project_or_404(db, project_id, current_user.user_id)

    stmt = select(Document).filter(Document.project_id == project_id)
    if not include_deleted:
        stmt = stmt.filter(Document.deleted_at.is_(None))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    docs = db.execute(
        stmt.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
    )

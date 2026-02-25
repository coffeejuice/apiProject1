from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.library.library_item import Library, LibraryType
from app.models.user import User
from app.schemas import LibraryListItemResponse, LibraryResponse

router = APIRouter(prefix="/library", tags=["library"])


def _list_by_type(db: Session, library_type: LibraryType) -> List[Library]:
    return db.execute(
        select(Library)
        .filter(Library.type == library_type)
        .order_by(Library.id.asc())
    ).scalars().all()


def _get_by_type_or_404(db: Session, item_id: int, library_type: LibraryType) -> Library:
    item = db.execute(
        select(Library).filter(
            Library.id == item_id,
            Library.type == library_type,
        )
    ).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    return item


@router.get("/dies", response_model=List[LibraryListItemResponse])
def list_dies(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.die)


@router.get("/dies/{item_id}", response_model=LibraryResponse)
def get_die(
    item_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.die)


@router.get("/die-assemblies", response_model=List[LibraryListItemResponse])
def list_die_assemblies(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.die_assembly)


@router.get("/die-assemblies/{item_id}", response_model=LibraryResponse)
def get_die_assembly(
    item_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.die_assembly)


@router.get("/presses", response_model=List[LibraryListItemResponse])
def list_presses(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.press)


@router.get("/presses/{item_id}", response_model=LibraryResponse)
def get_press(
    item_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.press)


@router.get("/press-modes", response_model=List[LibraryListItemResponse])
def list_press_modes(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.press_mode)


@router.get("/press-modes/{item_id}", response_model=LibraryResponse)
def get_press_mode(
    item_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.press_mode)


@router.get("/time-between-operations", response_model=List[LibraryListItemResponse])
def list_time_between_operations(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.time_between_operations)


@router.get("/time-between-operations/{item_id}", response_model=LibraryResponse)
def get_time_between_operation(
    item_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.time_between_operations)


@router.get("/operation-types", response_model=List[LibraryListItemResponse])
def list_operation_types(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.operation_type)


@router.get("/operation-types/{item_id}", response_model=LibraryResponse)
def get_operation_type(
    item_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.operation_type)

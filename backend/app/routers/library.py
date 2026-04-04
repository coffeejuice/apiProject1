from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.library.die import Die, DieAssembly, DieType
from app.models.library.material import Material
from app.models.library.library_item import Library, LibraryType
from app.models.library.press import Press, PressMode
from app.models.user import User as UserModel
from app.schemas import (
    LibraryDbDieAssemblyResponse,
    LibraryDbDieResponse,
    LibraryDbDieTypeResponse,
    LibraryDbMaterialResponse,
    LibraryDbPressModeResponse,
    LibraryDbPressResponse,
    LibraryDbUserResponse,
    LibraryListItemResponse,
    LibraryResponse,
)

router = APIRouter(prefix="/library", tags=["library"])


DIES_FILES_DIR = (Path(__file__).resolve().parents[2] / "data" / "dies").resolve()


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


def _build_die_stl_file_name(die_template_file_name: Optional[str]) -> Optional[str]:
    if not die_template_file_name:
        return None

    normalized_name = Path(die_template_file_name).name.strip()
    if not normalized_name:
        return None

    stem = Path(normalized_name).stem.strip()
    if not stem:
        return None

    return f"{stem}.stl"


def _resolve_die_asset_path(file_name: str) -> Path:
    safe_name = Path(file_name).name
    if safe_name != file_name:
        raise HTTPException(status_code=400, detail="Invalid die asset file name")

    resolved = (DIES_FILES_DIR / safe_name).resolve(strict=False)
    try:
        resolved.relative_to(DIES_FILES_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid die asset path") from exc

    return resolved


def _resolve_existing_die_stl_file_name(die_template_file_name: Optional[str]) -> Optional[str]:
    preferred_name = _build_die_stl_file_name(die_template_file_name)
    if not preferred_name:
        return None

    preferred_path = _resolve_die_asset_path(preferred_name)
    if preferred_path.is_file():
        return preferred_name

    uppercase_name = f"{Path(preferred_name).stem}.STL"
    uppercase_path = _resolve_die_asset_path(uppercase_name)
    if uppercase_path.is_file():
        return uppercase_name

    return preferred_name


@router.get("/dies", response_model=List[LibraryListItemResponse])
def list_dies(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.die)


@router.get("/dies/{item_id}", response_model=LibraryResponse)
def get_die(
    item_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.die)


@router.get("/die-assemblies", response_model=List[LibraryListItemResponse])
def list_die_assemblies(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.die_assembly)


@router.get("/die-assemblies/{item_id}", response_model=LibraryResponse)
def get_die_assembly(
    item_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.die_assembly)


@router.get("/presses", response_model=List[LibraryListItemResponse])
def list_presses(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.press)


@router.get("/presses/{item_id}", response_model=LibraryResponse)
def get_press(
    item_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.press)


@router.get("/press-modes", response_model=List[LibraryListItemResponse])
def list_press_modes(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.press_mode)


@router.get("/press-modes/{item_id}", response_model=LibraryResponse)
def get_press_mode(
    item_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.press_mode)


@router.get("/time-between-operations", response_model=List[LibraryListItemResponse])
def list_time_between_operations(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.time_between_operations)


@router.get("/time-between-operations/{item_id}", response_model=LibraryResponse)
def get_time_between_operation(
    item_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.time_between_operations)


@router.get("/operation-types", response_model=List[LibraryListItemResponse])
def list_operation_types(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _list_by_type(db, LibraryType.operation_type)


@router.get("/operation-types/{item_id}", response_model=LibraryResponse)
def get_operation_type(
    item_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_by_type_or_404(db, item_id, LibraryType.operation_type)


@router.get("/db/users", response_model=List[LibraryDbUserResponse])
def list_db_users(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(UserModel).order_by(UserModel.user_id.asc())
    ).scalars().all()


@router.get("/db/die-types", response_model=List[LibraryDbDieTypeResponse])
def list_db_die_types(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(DieType).order_by(DieType.id.asc())
    ).scalars().all()


@router.get("/db/materials", response_model=List[LibraryDbMaterialResponse])
def list_db_materials(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(Material).order_by(Material.material_id.asc())
    ).scalars().all()


@router.get("/db/dies", response_model=List[LibraryDbDieResponse])
def list_db_dies(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dies = db.execute(
        select(Die).order_by(Die.id.asc())
    ).scalars().all()

    serialized_dies: List[LibraryDbDieResponse] = []

    for die in dies:
        payload = LibraryDbDieResponse.model_validate(die)
        stl_file_name = _resolve_existing_die_stl_file_name(die.die_template_file_name)

        payload.stl_file_name = stl_file_name
        payload.stl_file_url = (
            f"/library/db/dies/stl/{quote(stl_file_name)}" if stl_file_name else None
        )
        payload.stl_file_exists = bool(
            stl_file_name and _resolve_die_asset_path(stl_file_name).is_file()
        )
        serialized_dies.append(payload)

    return serialized_dies


@router.get("/db/dies/stl/{file_name}")
def get_db_die_stl_file(
    file_name: str,
    _: UserModel = Depends(get_current_user),
):
    if not file_name.lower().endswith(".stl"):
        raise HTTPException(status_code=400, detail="Only STL files are allowed")

    file_path = _resolve_die_asset_path(file_name)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="STL file not found")

    return FileResponse(
        path=file_path,
        media_type="model/stl",
        filename=file_path.name,
    )


@router.get("/db/die-assemblies", response_model=List[LibraryDbDieAssemblyResponse])
def list_db_die_assemblies(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(DieAssembly).order_by(DieAssembly.id.asc())
    ).scalars().all()


@router.get("/db/presses", response_model=List[LibraryDbPressResponse])
def list_db_presses(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(Press).order_by(Press.id.asc())
    ).scalars().all()


@router.get("/db/press-modes", response_model=List[LibraryDbPressModeResponse])
def list_db_press_modes(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(PressMode).order_by(PressMode.id.asc())
    ).scalars().all()

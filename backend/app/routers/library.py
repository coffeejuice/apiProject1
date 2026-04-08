from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models.library.die import Die, DieAssembly, DieType
from app.models.library.material import Material
from app.models.library.material_classification import (
    MaterialClassificationAssignment,
    MaterialClassificationAxis,
    MaterialClassificationValue,
)
from app.models.library.material_standards import MaterialDesignation
from app.models.library.library_item import Library, LibraryType
from app.models.library.press import Press, PressMode
from app.models.user import User as UserModel
from app.schemas import (
    LibraryDbDieAssemblyResponse,
    LibraryDbDieResponse,
    LibraryDbDieTypeResponse,
    LibraryDbMaterialClassificationResponse,
    LibraryDbMaterialResponse,
    LibraryDbMaterialVisualResponse,
    LibraryDbPressModeResponse,
    LibraryDbPressResponse,
    LibraryDbUserResponse,
    LibraryListItemResponse,
    LibraryResponse,
)
from app.services.materials.errors import (
    MaterialFileNotFoundError,
    MaterialParserError,
    MaterialSourceNotSupportedError,
)
from app.services.materials.models import MaterialDiagram, MaterialVisualPayload
from app.services.materials.service import get_material_visual_payload

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


def _get_db_material_or_404(db: Session, material_id: int) -> Material:
    material = db.execute(
        select(Material).filter(Material.material_id == material_id)
    ).scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


def _serialize_material_visual_payload(payload: MaterialVisualPayload) -> dict:
    return {
        "material_id": payload.material_id,
        "source": payload.source.value,
        "file_name": payload.file_name,
        "diagrams": [_serialize_material_diagram(diagram) for diagram in payload.diagrams],
    }


def _serialize_material_classifications(material: Material) -> dict[str, list[str]]:
    grouped: dict[str, tuple[int, int, list[tuple[int, int, str]]]] = {}

    for assignment in material.classification_assignments:
        value = assignment.classification_value
        axis = value.axis if value else None
        if value is None or axis is None or axis.is_obsolete or value.is_obsolete:
            continue

        axis_hierarchy_level, axis_sort_order, values = grouped.setdefault(
            axis.key,
            (axis.hierarchy_level, axis.sort_order, []),
        )
        values.append((value.sort_order, value.value_id, value.key))
        grouped[axis.key] = (axis_hierarchy_level, axis_sort_order, values)

    serialized: dict[str, list[str]] = {}
    for axis_key, payload in sorted(
        grouped.items(),
        key=lambda entry: (entry[1][0], entry[1][1], entry[0]),
    ):
        serialized[axis_key] = [
            value_key
            for _, _, value_key in sorted(payload[2], key=lambda item: (item[0], item[1], item[2]))
        ]

    return serialized


def _serialize_material_designations(material: Material) -> list[str]:
    designations = [
        entry
        for entry in material.designations
        if not entry.is_obsolete and entry.designation and entry.designation.strip()
    ]
    designations.sort(
        key=lambda entry: (
            0 if entry.is_main_designation else 1,
            entry.designation.casefold(),
            entry.designation_id,
        )
    )
    return [entry.designation.strip() for entry in designations]


def _format_standard_label(designation: MaterialDesignation) -> str | None:
    standard = designation.standard
    if standard is None or standard.is_obsolete:
        return None

    number = (standard.standard_number or "").strip()
    organization = (standard.issue_organization or "").strip()
    if not number:
        return None

    if organization and not number.casefold().startswith(organization.casefold()):
        return f"{organization} {number}"
    return number


def _format_material_chemistry_limit_value(value: float | None) -> str | None:
    if value is None:
        return None
    return format(value, "g")


def _serialize_material_designation_chemistry_limits(designation: MaterialDesignation) -> dict[str, str]:
    rows = [
        row
        for row in designation.standard_chemistry_rows
        if not row.is_obsolete and row.element_symbol and row.element_symbol.strip()
    ]
    rows.sort(key=lambda row: (row.element_symbol.casefold(), row.standard_chemistry_id))

    limits: dict[str, str] = {}
    for row in rows:
        element_symbol = row.element_symbol.strip()

        if row.is_balance:
            limits[element_symbol] = "bal"
            continue

        min_value = _format_material_chemistry_limit_value(row.min_wt_pct)
        max_value = _format_material_chemistry_limit_value(row.max_wt_pct)

        if min_value is not None and max_value is not None:
            limits[element_symbol] = min_value if min_value == max_value else f"{min_value}-{max_value}"
        elif min_value is not None:
            limits[element_symbol] = f">{min_value}"
        elif max_value is not None:
            limits[element_symbol] = f"<{max_value}"

    return limits


def _serialize_material_standards(material: Material) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for designation in sorted(
        material.designations,
        key=lambda entry: (
            0 if entry.is_main_designation else 1,
            entry.designation.casefold(),
            entry.designation_id,
        ),
    ):
        if designation.is_obsolete:
            continue
        label = _format_standard_label(designation)
        if not label:
            continue
        normalized = label.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        labels.append(label)
    return labels


def _serialize_material_designation_links(material: Material) -> list[dict[str, str | bool | None]]:
    rows: list[dict[str, str | bool | None]] = []
    for designation in material.designations:
        if designation.is_obsolete or not designation.designation or not designation.designation.strip():
            continue
        standard = designation.standard
        standard_label = _format_standard_label(designation)
        country = None
        if standard is not None and not standard.is_obsolete:
            country = (standard.country_or_region or "").strip() or None
        rows.append(
            {
                "designation": designation.designation.strip(),
                "standard": standard_label,
                "country": country,
                "chemistry_limits": _serialize_material_designation_chemistry_limits(designation),
                "is_main_designation": designation.is_main_designation,
            }
        )
    rows.sort(
        key=lambda entry: (
            1 if entry["standard"] is None else 0,
            (entry["standard"] or "").casefold(),
            str(entry["designation"]).casefold(),
        )
    )
    return rows


def _count_material_test_records(material: Material) -> int:
    return sum(1 for entry in material.test_records if not entry.is_obsolete)


def _serialize_db_material(material: Material) -> dict:
    return LibraryDbMaterialResponse(
        material_id=material.material_id,
        name=material.name,
        deform_file_name=material.deform_file_name,
        note=material.note,
        classifications=_serialize_material_classifications(material),
        designations=_serialize_material_designations(material),
        standards=_serialize_material_standards(material),
        designation_links=_serialize_material_designation_links(material),
        test_records_count=_count_material_test_records(material),
        is_obsolete=material.is_obsolete,
        owner_id=material.owner_id,
    ).model_dump()


def _serialize_material_classification_catalog(axes: list[MaterialClassificationAxis]) -> dict:
    return {
        "axes": [
            {
                "axis_id": axis.axis_id,
                "key": axis.key,
                "name": axis.name,
                "description": axis.description,
                "selection_mode": axis.selection_mode,
                "hierarchy_level": axis.hierarchy_level,
                "sort_order": axis.sort_order,
                "is_filter_visible": axis.is_filter_visible,
                "is_obsolete": axis.is_obsolete,
                "created_at": axis.created_at,
                "created_by_user_id": axis.created_by_user_id,
                "values": [
                    {
                        "value_id": value.value_id,
                        "axis_id": value.axis_id,
                        "key": value.key,
                        "name": value.name,
                        "color": value.color,
                        "sort_order": value.sort_order,
                        "is_obsolete": value.is_obsolete,
                        "created_at": value.created_at,
                        "created_by_user_id": value.created_by_user_id,
                    }
                    for value in sorted(axis.values, key=lambda entry: (entry.sort_order, entry.value_id))
                ],
            }
            for axis in sorted(axes, key=lambda entry: (entry.hierarchy_level, entry.sort_order, entry.axis_id))
        ]
    }


def _serialize_material_diagram(diagram: MaterialDiagram) -> dict:
    return {
        "key": diagram.key,
        "title": diagram.title,
        "kind": diagram.kind,
        "x_axis": {
            "key": diagram.x_axis.key,
            "label": diagram.x_axis.label,
            "unit": diagram.x_axis.unit,
        },
        "y_axis": {
            "key": diagram.y_axis.key,
            "label": diagram.y_axis.label,
            "unit": diagram.y_axis.unit,
        },
        "series": [
            {
                "key": series.key,
                "label": series.label,
                "points": [{"x": point.x, "y": point.y} for point in series.points],
            }
            for series in diagram.series
        ],
        "controls": diagram.controls,
    }


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
    materials = db.execute(
        select(Material)
        .options(
            selectinload(Material.classification_assignments)
            .selectinload(MaterialClassificationAssignment.classification_value)
            .selectinload(MaterialClassificationValue.axis),
            selectinload(Material.designations).selectinload(MaterialDesignation.standard),
            selectinload(Material.designations).selectinload(MaterialDesignation.standard_chemistry_rows),
            selectinload(Material.test_records),
        )
        .order_by(Material.material_id.asc())
    ).scalars().all()
    return [_serialize_db_material(material) for material in materials]


@router.get("/db/material-classification", response_model=LibraryDbMaterialClassificationResponse)
def get_db_material_classification(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    axes = db.execute(
        select(MaterialClassificationAxis)
        .options(selectinload(MaterialClassificationAxis.values))
        .order_by(MaterialClassificationAxis.sort_order.asc(), MaterialClassificationAxis.axis_id.asc())
    ).scalars().all()
    return _serialize_material_classification_catalog(axes)


@router.get("/db/materials/{material_id}/visuals", response_model=LibraryDbMaterialVisualResponse)
def get_db_material_visuals(
    material_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = _get_db_material_or_404(db, material_id)

    try:
        payload = get_material_visual_payload(material)
    except MaterialFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MaterialSourceNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MaterialParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _serialize_material_visual_payload(payload)


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

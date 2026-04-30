from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
from app.models.library.material_chemistry import (
    MaterialChemistryTestResult,
    MaterialDesignationStandardChemistry,
    MaterialTestRecord,
    PublicationCatalog,
)
from app.models.library.material_properties import (
    MaterialPropertyColumnValue,
    MaterialPropertyTable,
    MaterialPropertyTableColumn,
)
from app.models.library.material_standards import MaterialDesignation, MaterialStandardCatalog
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
    MaterialDeleteRequest,
    MaterialDeleteResponse,
    MaterialCopyRequest,
    MaterialCopyResponse,
    MaterialDeformFileUploadResponse,
    LibraryDbPressModeResponse,
    LibraryDbPressResponse,
    LibraryDbUserResponse,
    LibraryListItemResponse,
    LibraryResponse,
    MaterialStandardCatalogItemResponse,
    MaterialWorkspaceDesignationResponse,
    MaterialWorkspaceDesignationInput,
    MaterialWorkspaceResponse,
    MaterialWorkspaceTestRecordSummaryResponse,
    MaterialWorkspaceUpsertRequest,
)
from app.services.materials.errors import (
    MaterialFileNotFoundError,
    MaterialParserError,
    MaterialSourceNotSupportedError,
)
from app.services.materials.models import MaterialDiagram, MaterialVisualPayload
from app.services.materials.service import MATERIALS_FILES_DIR, get_material_visual_payload

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
        select(Material).filter(
            Material.material_id == material_id,
            Material.is_obsolete.is_(False),
        )
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
    if standard is None:
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


def _build_unique_material_upload_path(original_name: str) -> Path:
    safe_name = Path(original_name).name.strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Uploaded file must have a name")

    suffix = Path(safe_name).suffix
    stem = Path(safe_name).stem
    if suffix.lower() != ".key":
        raise HTTPException(status_code=400, detail="Only .key / .KEY files are allowed")

    MATERIALS_FILES_DIR.mkdir(parents=True, exist_ok=True)

    candidate = MATERIALS_FILES_DIR / safe_name
    counter = 1
    while candidate.exists():
        candidate = MATERIALS_FILES_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    return candidate


def _material_workspace_query():
    return (
        select(Material)
        .options(
            selectinload(Material.classification_assignments)
            .selectinload(MaterialClassificationAssignment.classification_value)
            .selectinload(MaterialClassificationValue.axis),
            selectinload(Material.designations).selectinload(MaterialDesignation.standard),
            selectinload(Material.designations).selectinload(MaterialDesignation.standard_chemistry_rows),
            selectinload(Material.test_records).selectinload(MaterialTestRecord.designation),
            selectinload(Material.test_records).selectinload(MaterialTestRecord.publication),
            selectinload(Material.test_records).selectinload(MaterialTestRecord.chemistry_results),
            selectinload(Material.test_records)
            .selectinload(MaterialTestRecord.property_tables)
            .selectinload(MaterialPropertyTable.columns)
            .selectinload(MaterialPropertyTableColumn.values),
        )
    )


def _get_db_material_with_workspace_or_404(db: Session, material_id: int) -> Material:
    material = db.execute(
        _material_workspace_query().filter(
            Material.material_id == material_id,
            Material.is_obsolete.is_(False),
        )
    ).scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _serialize_material_workspace_designation(
    designation: MaterialDesignation,
) -> MaterialWorkspaceDesignationResponse:
    standard = designation.standard
    country = None
    if standard is not None:
        country = _normalize_optional_text(standard.country_or_region)

    return MaterialWorkspaceDesignationResponse(
        designation_id=designation.designation_id,
        designation=designation.designation.strip(),
        standard_id=designation.standard_id,
        standard_label=_format_standard_label(designation),
        country=country,
        note=designation.note,
        is_main_designation=designation.is_main_designation,
    )


def _serialize_material_workspace_test_record(
    test_record: MaterialTestRecord,
) -> MaterialWorkspaceTestRecordSummaryResponse:
    designation = test_record.designation
    publication = test_record.publication
    return MaterialWorkspaceTestRecordSummaryResponse(
        test_record_id=test_record.test_record_id,
        designation_id=designation.designation_id if designation and not designation.is_obsolete else None,
        designation=designation.designation if designation and not designation.is_obsolete else None,
        publication_id=publication.publication_id if publication and not publication.is_obsolete else None,
        publication_title=publication.title if publication and not publication.is_obsolete else None,
        heat_number=test_record.heat_number,
        batch_number=test_record.batch_number,
        sample_label=test_record.sample_label,
        note=test_record.note,
        chemistry_results_count=sum(1 for row in test_record.chemistry_results),
        property_tables_count=sum(1 for row in test_record.property_tables if not row.is_obsolete),
    )


def _serialize_material_workspace(material: Material) -> MaterialWorkspaceResponse:
    active_designations = [
        entry
        for entry in material.designations
        if not entry.is_obsolete and entry.designation and entry.designation.strip()
    ]
    active_designations.sort(
        key=lambda entry: (
            0 if entry.is_main_designation else 1,
            1 if _format_standard_label(entry) is None else 0,
            (_format_standard_label(entry) or "").casefold(),
            entry.designation.casefold(),
            entry.designation_id,
        )
    )

    active_test_records = [entry for entry in material.test_records if not entry.is_obsolete]
    active_test_records.sort(key=lambda entry: entry.test_record_id)

    return MaterialWorkspaceResponse(
        material_id=material.material_id,
        name=material.name,
        deform_file_name=material.deform_file_name,
        note=material.note,
        classifications=_serialize_material_classifications(material),
        designations=[
            _serialize_material_workspace_designation(entry) for entry in active_designations
        ],
        test_records=[
            _serialize_material_workspace_test_record(entry) for entry in active_test_records
        ],
        is_obsolete=material.is_obsolete,
        owner_id=material.owner_id,
    )


def _serialize_standard_catalog_item(standard: MaterialStandardCatalog) -> dict:
    number = (standard.standard_number or "").strip()
    organization = _normalize_optional_text(standard.issue_organization)
    label = number
    if organization and number and not number.casefold().startswith(organization.casefold()):
        label = f"{organization} {number}"

    return MaterialStandardCatalogItemResponse(
        standard_id=standard.standard_id,
        standard_number=standard.standard_number,
        issue_organization=standard.issue_organization,
        country_or_region=standard.country_or_region,
        geographic_level=standard.geographic_level.value if standard.geographic_level else None,
        label=label,
    ).model_dump()


def _replace_material_classifications(
    *,
    db: Session,
    material: Material,
    classifications: Dict[str, List[str]],
    current_user_id: Optional[int],
) -> None:
    axis_keys = [axis_key for axis_key, value_keys in classifications.items() if value_keys]
    selected_value_keys = {
        (axis_key, value_key)
        for axis_key, value_keys in classifications.items()
        for value_key in value_keys
    }

    if not axis_keys:
        material.classification_assignments.clear()
        return

    values = db.execute(
        select(MaterialClassificationValue)
        .join(MaterialClassificationAxis, MaterialClassificationValue.axis_id == MaterialClassificationAxis.axis_id)
        .filter(MaterialClassificationAxis.key.in_(axis_keys))
    ).scalars().all()
    values_by_axis_key = {
        (value.axis.key, value.key): value
        for value in values
        if value.axis is not None and not value.is_obsolete and not value.axis.is_obsolete
    }

    missing = sorted(selected_value_keys - set(values_by_axis_key.keys()))
    if missing:
        missing_labels = ", ".join(f"{axis_key}:{value_key}" for axis_key, value_key in missing)
        raise HTTPException(status_code=422, detail=f"Unknown classification values: {missing_labels}")

    material.classification_assignments.clear()
    for axis_key, value_keys in classifications.items():
        for value_key in value_keys:
            value = values_by_axis_key[(axis_key, value_key)]
            material.classification_assignments.append(
                MaterialClassificationAssignment(
                    value_id=value.value_id,
                    created_by_user_id=current_user_id,
                )
            )


def _upsert_designation_standard_chemistry_rows(
    target: MaterialDesignation,
    source: MaterialDesignation,
) -> None:
    rows_by_element = {
        row.element_symbol.strip().casefold(): row
        for row in target.standard_chemistry_rows
        if row.element_symbol and row.element_symbol.strip()
    }
    for source_row in source.standard_chemistry_rows:
        if source_row.is_obsolete or not source_row.element_symbol or not source_row.element_symbol.strip():
            continue
        key = source_row.element_symbol.strip().casefold()
        target_row = rows_by_element.get(key)
        if target_row is None:
            target_row = MaterialDesignationStandardChemistry(
                element_symbol=source_row.element_symbol.strip(),
            )
            target.standard_chemistry_rows.append(target_row)
            rows_by_element[key] = target_row

        target_row.min_wt_pct = source_row.min_wt_pct
        target_row.max_wt_pct = source_row.max_wt_pct
        target_row.is_balance = source_row.is_balance
        target_row.note = source_row.note
        target_row.is_obsolete = source_row.is_obsolete


def _sync_material_designations(
    *,
    db: Session,
    material: Material,
    payload_designations: List[MaterialWorkspaceDesignationInput],
) -> None:
    designations_by_id = {entry.designation_id: entry for entry in material.designations}
    payload_ids = {
        entry.designation_id
        for entry in payload_designations
        if entry.designation_id is not None
    }

    for designation in material.designations:
        if designation.designation_id not in payload_ids:
            designation.is_obsolete = True

    main_found = False
    for payload in payload_designations:
        normalized_designation = payload.designation.strip()
        if payload.standard_id is not None:
            standard = db.execute(
                select(MaterialStandardCatalog).filter(
                    MaterialStandardCatalog.standard_id == payload.standard_id,
                )
            ).scalars().first()
            if standard is None:
                raise HTTPException(status_code=422, detail=f"Unknown standard id: {payload.standard_id}")

        designation = designations_by_id.get(payload.designation_id or -1)
        if designation is None:
            designation = MaterialDesignation(material_id=material.material_id)
            material.designations.append(designation)

        designation.designation = normalized_designation
        designation.standard_id = payload.standard_id
        designation.note = _normalize_optional_text(payload.note)
        designation.is_obsolete = False
        designation.is_main_designation = bool(payload.is_main_designation) and not main_found
        if designation.is_main_designation:
            main_found = True

    active_designations = [entry for entry in material.designations if not entry.is_obsolete]
    if active_designations and not any(entry.is_main_designation for entry in active_designations):
        active_designations[0].is_main_designation = True


def _ensure_target_designation_from_source(
    *,
    target_material: Material,
    source_designation: MaterialDesignation,
) -> tuple[MaterialDesignation, bool]:
    normalized_designation = source_designation.designation.strip()
    for candidate in target_material.designations:
        if candidate.is_obsolete:
            continue
        if (
            candidate.designation.strip().casefold() == normalized_designation.casefold()
            and candidate.standard_id == source_designation.standard_id
        ):
            _upsert_designation_standard_chemistry_rows(candidate, source_designation)
            return candidate, False

    target_designation = MaterialDesignation(
        designation=normalized_designation,
        standard_id=source_designation.standard_id,
        is_main_designation=False,
        note=source_designation.note,
        is_obsolete=False,
    )
    target_material.designations.append(target_designation)
    _upsert_designation_standard_chemistry_rows(target_designation, source_designation)
    return target_designation, True


def _clone_property_table(source_table: MaterialPropertyTable) -> MaterialPropertyTable:
    cloned_table = MaterialPropertyTable(
        property_type=source_table.property_type,
        representation_kind=source_table.representation_kind,
        replicate_no=source_table.replicate_no,
        conditions=source_table.conditions,
        title=source_table.title,
        note=source_table.note,
        is_obsolete=source_table.is_obsolete,
    )
    for source_column in source_table.columns:
        cloned_column = MaterialPropertyTableColumn(
            column_property_type=source_column.column_property_type,
            column_units=source_column.column_units,
            sort_order=source_column.sort_order,
        )
        for source_value in source_column.values:
            cloned_column.values.append(
                MaterialPropertyColumnValue(
                    point_index=source_value.point_index,
                    value=source_value.value,
                )
            )
        cloned_table.columns.append(cloned_column)
    return cloned_table


def _copy_test_records_to_material(
    *,
    target_material: Material,
    source_test_records: List[MaterialTestRecord],
) -> int:
    copied_count = 0
    for source_record in source_test_records:
        target_designation = None
        if source_record.designation and not source_record.designation.is_obsolete:
            target_designation, _ = _ensure_target_designation_from_source(
                target_material=target_material,
                source_designation=source_record.designation,
            )

        cloned_record = MaterialTestRecord(
            material_id=target_material.material_id,
            designation=target_designation,
            publication_id=source_record.publication_id,
            heat_number=source_record.heat_number,
            batch_number=source_record.batch_number,
            sample_label=source_record.sample_label,
            test_date=source_record.test_date,
            note=source_record.note,
            is_obsolete=source_record.is_obsolete,
        )

        for chemistry_row in source_record.chemistry_results:
            cloned_record.chemistry_results.append(
                MaterialChemistryTestResult(
                    element_symbol=chemistry_row.element_symbol,
                    actual_wt_pct=chemistry_row.actual_wt_pct,
                )
            )

        for property_table in source_record.property_tables:
            cloned_record.property_tables.append(_clone_property_table(property_table))

        target_material.test_records.append(cloned_record)
        copied_count += 1

    return copied_count


def _apply_material_workspace_payload(
    *,
    db: Session,
    material: Material,
    payload: MaterialWorkspaceUpsertRequest,
    current_user_id: Optional[int],
) -> None:
    material.name = payload.name.strip()
    material.deform_file_name = _normalize_optional_text(payload.deform_file_name)
    material.note = _normalize_optional_text(payload.note)
    material.is_obsolete = payload.is_obsolete

    _replace_material_classifications(
        db=db,
        material=material,
        classifications=payload.classifications,
        current_user_id=current_user_id,
    )
    _sync_material_designations(
        db=db,
        material=material,
        payload_designations=payload.designations,
    )

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
        .filter(Material.is_obsolete.is_(False))
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


@router.get("/db/material-standards", response_model=List[MaterialStandardCatalogItemResponse])
def list_db_material_standards(
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    standards = db.execute(
        select(MaterialStandardCatalog)
        .filter(MaterialStandardCatalog.is_obsolete.is_(False))
        .order_by(
            MaterialStandardCatalog.issue_organization.asc().nulls_last(),
            MaterialStandardCatalog.standard_number.asc(),
            MaterialStandardCatalog.standard_id.asc(),
        )
    ).scalars().all()
    return [_serialize_standard_catalog_item(standard) for standard in standards]


@router.post("/db/materials/upload-deform-file", response_model=MaterialDeformFileUploadResponse)
async def upload_db_material_deform_file(
    file: UploadFile = File(...),
    _: UserModel = Depends(get_current_user),
):
    target_path = _build_unique_material_upload_path(file.filename or "")
    file_bytes = await file.read()
    await file.close()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    target_path.write_bytes(file_bytes)
    return MaterialDeformFileUploadResponse(file_name=target_path.name)


@router.get("/db/materials/{material_id}/workspace", response_model=MaterialWorkspaceResponse)
def get_db_material_workspace(
    material_id: int,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = _get_db_material_with_workspace_or_404(db, material_id)
    return _serialize_material_workspace(material)


@router.post("/db/materials/workspace", response_model=MaterialWorkspaceResponse)
def create_db_material_workspace(
    payload: MaterialWorkspaceUpsertRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = Material(
        name=payload.name.strip(),
        deform_file_name=_normalize_optional_text(payload.deform_file_name),
        note=_normalize_optional_text(payload.note),
        is_obsolete=payload.is_obsolete,
        owner_id=current_user.user_id,
    )
    db.add(material)
    db.flush()

    _apply_material_workspace_payload(
        db=db,
        material=material,
        payload=payload,
        current_user_id=current_user.user_id,
    )

    db.commit()
    refreshed = _get_db_material_with_workspace_or_404(db, material.material_id)
    return _serialize_material_workspace(refreshed)


@router.patch("/db/materials/{material_id}/workspace", response_model=MaterialWorkspaceResponse)
def update_db_material_workspace(
    material_id: int,
    payload: MaterialWorkspaceUpsertRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = _get_db_material_with_workspace_or_404(db, material_id)
    _apply_material_workspace_payload(
        db=db,
        material=material,
        payload=payload,
        current_user_id=current_user.user_id,
    )
    db.commit()
    refreshed = _get_db_material_with_workspace_or_404(db, material.material_id)
    return _serialize_material_workspace(refreshed)


@router.delete("/db/materials", response_model=MaterialDeleteResponse)
def delete_db_materials(
    payload: MaterialDeleteRequest,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requested_ids = sorted({material_id for material_id in payload.material_ids})
    materials = db.execute(
        _material_workspace_query().filter(
            Material.material_id.in_(requested_ids),
            Material.is_obsolete.is_(False),
        )
    ).scalars().unique().all()

    if not materials:
        raise HTTPException(status_code=404, detail="No active materials found for deletion")

    deleted_material_ids: list[int] = []
    for material in materials:
        material.is_obsolete = True
        for designation in material.designations:
            designation.is_obsolete = True
            for chemistry_row in designation.standard_chemistry_rows:
                chemistry_row.is_obsolete = True
        for test_record in material.test_records:
            test_record.is_obsolete = True
            for property_table in test_record.property_tables:
                property_table.is_obsolete = True
        deleted_material_ids.append(material.material_id)

    db.commit()
    return MaterialDeleteResponse(
        deleted_material_ids=deleted_material_ids,
        deleted_count=len(deleted_material_ids),
    )


@router.post("/db/materials/copy", response_model=MaterialCopyResponse)
def copy_db_material_data(
    payload: MaterialCopyRequest,
    _: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.source_material_id == payload.target_material_id:
        raise HTTPException(status_code=422, detail="Source and target materials must be different")

    source_material = _get_db_material_with_workspace_or_404(db, payload.source_material_id)
    target_material = _get_db_material_with_workspace_or_404(db, payload.target_material_id)

    copied_identity_fields: List[str] = []
    if "note" in payload.copy_identity_fields:
        target_material.note = source_material.note
        copied_identity_fields.append("note")
    if "deform_file_name" in payload.copy_identity_fields:
        target_material.deform_file_name = source_material.deform_file_name
        copied_identity_fields.append("deform_file_name")

    copied_classification_assignments_count = 0
    if payload.copy_classifications:
        if payload.replace_classifications:
            target_material.classification_assignments.clear()
        existing_value_ids = {
            assignment.value_id for assignment in target_material.classification_assignments
        }
        for assignment in source_material.classification_assignments:
            if assignment.value_id in existing_value_ids:
                continue
            target_material.classification_assignments.append(
                MaterialClassificationAssignment(value_id=assignment.value_id)
            )
            existing_value_ids.add(assignment.value_id)
            copied_classification_assignments_count += 1

    selected_source_designations = [
        designation
        for designation in source_material.designations
        if not designation.is_obsolete
        and (
            not payload.designation_ids
            or designation.designation_id in set(payload.designation_ids)
        )
    ]

    copied_designations_count = 0
    if payload.copy_designations:
        if payload.replace_designations:
            for designation in target_material.designations:
                designation.is_obsolete = True
        for source_designation in selected_source_designations:
            _, created = _ensure_target_designation_from_source(
                target_material=target_material,
                source_designation=source_designation,
            )
            if created:
                copied_designations_count += 1

    selected_test_record_ids = set(payload.test_record_ids)
    source_test_records = [
        record
        for record in source_material.test_records
        if not record.is_obsolete
        and (not selected_test_record_ids or record.test_record_id in selected_test_record_ids)
    ]
    copied_test_records_count = 0
    if payload.copy_test_records:
        copied_test_records_count = _copy_test_records_to_material(
            target_material=target_material,
            source_test_records=source_test_records,
        )

    db.commit()

    return MaterialCopyResponse(
        target_material_id=target_material.material_id,
        copied_identity_fields=copied_identity_fields,
        copied_designations_count=copied_designations_count,
        copied_test_records_count=copied_test_records_count,
        copied_classification_assignments_count=copied_classification_assignments_count,
    )


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

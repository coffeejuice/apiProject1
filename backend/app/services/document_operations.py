"""Materialize effective document operations from explicit document blocks."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document.block import Block
from app.models.document.document import Document, DocumentVersion
from app.models.document.document_operation import DocumentOperation
from app.models.document.block_types.document_geometry import GEOMETRY_TYPES
from app.models.workflow_runtime import SimulationStep, SimulationStepStatus, SimulationStepStatusEnum
from app.models.library.material import Material, MaterialVersion
from app.models.project import Project
from app.services.block_props import (
    DEFORMATION_PROPERTIES,
    DOCUMENT_PROPERTIES,
    FURNACE_PROPERTIES,
    OPERATION_PROPERTIES,
    as_dict,
    deep_merge,
    extract_namespace,
    normalize_deformation_block_props,
    normalize_document_block_props,
    normalize_furnace_block_props,
    normalize_heating_block_props,
    normalize_operation_block_props,
)
from app.services.preprocessor.operation_keys import DOCUMENT_INITIAL_DATA_TEMPLATE_ID, FURNACE_TEMPLATE_ID


DOCUMENT_BLOCK_TYPE_ID = "document"
HEATING_BLOCK_TYPE_ID = "heating"
DEFORMATION_BLOCK_TYPE_ID = "deformation"
FURNACE_BLOCK_TYPE_ID = "furnace"
OPERATION_BLOCK_TYPE_ID = "operation"
EMPTY_OPERATION_TEMPLATE_ID = "operation.empty"
PARSER_OPERATION_BLOCK_TEMPLATE_IDS = frozenset(
    {
        "operation.upsetting",
        "operation.tail_flattening",
        "operation.tail_chamfering",
        "operation.cogging",
        "operation.rounding",
        "operation.radial",
        "operation.transversal",
        "operation.cut",
    }
)
GENERATED_OPERATION_LABELS: dict[str, tuple[str, str]] = {
    "upsetting.rotation_height": ("Upsetting: rotation and height", "upsetting"),
    "upsetting.tail_flattening": ("Upsetting: tail flattening", "upsetting"),
    "upsetting.single_stroke": ("Upsetting: single stroke", "upsetting"),
    "upsetting.three_strokes": ("Upsetting: three strokes", "upsetting"),
    "upsetting.tail_chamfering": ("Upsetting: tail chamfering", "upsetting"),
    "prolongation.rotation_height": ("Prolongation: rotation and height", "prolongation"),
    "prolongation.height_bites": ("Prolongation: height and bites", "prolongation"),
    "prolongation.skip_bites": ("Prolongation: skip bites", "prolongation"),
    "rounding.spiral_one_rotation": ("Spiral rounding: one rotation per feed", "prolongation"),
    "rounding.spiral_three_rotations": ("Spiral rounding: three rotations per feed", "prolongation"),
    "radial.rotation_height_feed": ("Radial: rotation, height and feed", "radial"),
    "radial.height_bites": ("Radial: height and number of bites", "radial"),
    "radial.press_axis_feed": ("Radial: press-axis feed", "radial"),
    "radial.initial_rotations": ("Radial: initial rotations", "radial"),
    "transverse.all_in_one": ("Transverse cogging: all in one", "transversal"),
    "transversal.rotation_height": ("Transversal cogging: rotation and height", "transversal"),
    "cutting.hot_keep_percent": ("Hot cutting: keep percent", "cutting"),
    "cutting.cold_saw_keep_percent": ("Cold saw: keep percent", "cutting"),
}
DEFAULT_MATERIAL_DENSITY_KG_PER_MM3 = 7.85e-6
FEED_DIRECTION_RIGHT_ID = 2
FEED_DIRECTION_LEFT_ID = 3
FEED_DIRECTION_BIDIRECTIONAL_ID = 4
FEED_DIRECTION_DEFAULT_ID = FEED_DIRECTION_RIGHT_ID
FEED_DIRECTION_ALLOWED_IDS = {
    FEED_DIRECTION_RIGHT_ID,
    FEED_DIRECTION_LEFT_ID,
    FEED_DIRECTION_BIDIRECTIONAL_ID,
}
FEED_SETTINGS_KEY = "feed_settings"
FEED_DIRECTION_FIELD = "feed_direction_id"
FEED_VALUE_FIELDS = ("feed_first", "feed_middle", "feed_last")
DEFORMATION_DIE_PARAMETER_FIELDS = ("die_assembly_id", "top_die_id", "bottom_die_id")
DEFORMATION_UPSETTING_SPEED_FIELD = "speed_upsetting"
DEFORMATION_PROLONGATION_SPEED_FIELD = "speed_prolongation"
STANDARD_RIGHT_ARROW = "→"
RIGHT_ARROW_SYMBOLS = (
    "→",
    "↠",
    "↣",
    "↦",
    "↪",
    "↬",
    "⇀",
    "⇁",
    "⇉",
    "⇛",
    "⇝",
    "⇢",
    "⇨",
    "⇒",
    "⇾",
    "➔",
    "➙",
    "➜",
    "➝",
    "➞",
    "➟",
    "➠",
    "➡",
    "➢",
    "➣",
    "➤",
    "➥",
    "➦",
    "➧",
    "➨",
    "➩",
    "➪",
    "➫",
    "➬",
    "➭",
    "➮",
    "➯",
    "➱",
    "➲",
    "➳",
    "➵",
    "➸",
    "➺",
    "➻",
    "➼",
    "➽",
    "➾",
    "⟶",
    "⟴",
    "⟹",
    "⟼",
    "⟾",
    "⟿",
    "⤀",
    "⤏",
    "⤐",
    "⤳",
    "⥤",
    "⭢",
    "⮕",
)
RIGHT_ARROW_PATTERN = re.compile(r"-->|->|" + "|".join(re.escape(symbol) for symbol in RIGHT_ARROW_SYMBOLS))
DECIMAL_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
INTEGER_PATTERN = r"[+-]?\d+"
INITIAL_STATE_RE = re.compile(rf"^\(\s*(?P<size>{DECIMAL_PATTERN})\s*\)$")
HEIGHT_PATTERN_RE = re.compile(
    rf"^(?:\(\s*(?P<rotation>{DECIMAL_PATTERN})\s*\)\s*)?"
    rf"(?P<height>{DECIMAL_PATTERN})"
    rf"(?:\s*\(\s*(?P<num_of_bites>\d+)\s*\))?"
    rf"(?:\s*\(\s*(?P<skip_bites>\d+(?:\s*,\s*\d+)*)\s*\))?$"
)
RADIAL_INITIAL_RE = re.compile(
    rf"^xyxy\s*\(\s*"
    rf"(?P<rotation_1_x>{DECIMAL_PATTERN})\s*,\s*"
    rf"(?P<rotation_2_y>{DECIMAL_PATTERN})\s*,\s*"
    rf"(?P<rotation_3_x>{DECIMAL_PATTERN})\s*,\s*"
    rf"(?P<rotation_4_y>{DECIMAL_PATTERN})\s*\)$",
    re.IGNORECASE,
)


def normalize_props_for_block_type(block_type_id: str, props: Mapping[str, Any] | None) -> dict[str, Any]:
    if block_type_id == DOCUMENT_BLOCK_TYPE_ID:
        return normalize_document_block_props(props)
    if block_type_id == HEATING_BLOCK_TYPE_ID:
        return normalize_heating_block_props(props)
    if block_type_id == DEFORMATION_BLOCK_TYPE_ID:
        return normalize_deformation_block_props(props)
    if block_type_id == FURNACE_BLOCK_TYPE_ID:
        return normalize_furnace_block_props(props)
    if block_type_id == OPERATION_BLOCK_TYPE_ID:
        return normalize_operation_block_props(props)
    return dict(props or {})


def _ordered_blocks(session: Session, document_id: int) -> list[Block]:
    from app.services.block_service import get_ordered_blocks

    return get_ordered_blocks(session, document_id)


def _operation_kind_from_template(template_id: str | None, operation_properties: Mapping[str, Any]) -> str:
    value = operation_properties.get("operation_kind")
    if value:
        return str(value)
    if not template_id:
        return "generic"
    return str(template_id).split(".", 1)[0]


def _operation_label(operation_properties: Mapping[str, Any]) -> str | None:
    snapshot = operation_properties.get("template_snapshot")
    if isinstance(snapshot, Mapping):
        for key in ("display_name", "label", "id"):
            value = snapshot.get(key)
            if value:
                return str(value)
    template_id = operation_properties.get("operation_template_id")
    return str(template_id) if template_id else None


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    formatter = getattr(value, "isoformat", None)
    if callable(formatter):
        return str(formatter())
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_document_version(session: Session, document_id: int) -> DocumentVersion | None:
    return session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.document_version_id.desc())
    ).first()


def _document_material_id(
    session: Session,
    document: Document | None,
    document_properties: Mapping[str, Any],
) -> int | None:
    block_material_id = _coerce_int(document_properties.get("material_id"))
    if block_material_id is not None:
        return block_material_id
    if document is None:
        return None
    if document.material_version_id is not None:
        material_version = session.get(MaterialVersion, document.material_version_id)
        if material_version is not None:
            return material_version.material_id
    project = session.get(Project, document.project_id)
    return project.material_id if project is not None else None


def _infer_volume_mm3(document_properties: Mapping[str, Any]) -> float | None:
    explicit_volume = _coerce_float(document_properties.get("volume_mm3"))
    if explicit_volume is not None and explicit_volume > 0.0:
        return explicit_volume

    attributes = as_dict(document_properties.get("attributes"))
    explicit_volume = _coerce_float(attributes.get("volume_mm3"))
    if explicit_volume is not None and explicit_volume > 0.0:
        return explicit_volume

    weight_kg = _coerce_float(document_properties.get("weight"))
    if weight_kg is None or weight_kg <= 0.0:
        return None

    density = _coerce_float(attributes.get("density_kg_per_mm3")) or DEFAULT_MATERIAL_DENSITY_KG_PER_MM3
    if density <= 0.0:
        return None
    return weight_kg / density


def _document_initial_target(
    session: Session,
    *,
    document_id: int,
    document_properties: Mapping[str, Any],
) -> dict[str, Any]:
    document = session.get(Document, document_id)
    version = _latest_document_version(session, document_id)
    material_id = _document_material_id(session, document, document_properties)
    material = session.get(Material, material_id) if material_id is not None else None
    material_version = (
        session.get(MaterialVersion, document.material_version_id)
        if document is not None and document.material_version_id is not None
        else None
    )

    geometry_type_id = str(document_properties.get("geometry_type_id") or "")
    geometry_metadata = GEOMETRY_TYPES.get(geometry_type_id, {})
    attributes = as_dict(document_properties.get("attributes"))

    return {
        "document_info": {
            "document_id": document.document_id if document is not None else document_id,
            "name": document.name if document is not None else document_properties.get("name"),
            "project_id": document.project_id if document is not None else None,
            "source_document_id": document.source_document_id if document is not None else None,
            "editor_user_id": document.editor_user_id if document is not None else None,
            "material_version_id": document.material_version_id if document is not None else None,
            "created_at": _isoformat(document.created_at) if document is not None else None,
            "updated_at": _isoformat(document.updated_at) if document is not None else None,
            "section_numbering_start": document_properties.get("section_numbering_start", 2),
            "version": {
                "document_version_id": version.document_version_id if version is not None else None,
                "name": version.name if version is not None else None,
                "is_editable": version.is_editable if version is not None else None,
                "execution_order": version.execution_order if version is not None else None,
                "operations_count": version.operations_count if version is not None else None,
                "created_at": _isoformat(version.created_at) if version is not None else None,
                "last_modified": _isoformat(version.last_modified) if version is not None else None,
            },
        },
        "process_data": {
            "heat_no": document_properties.get("heat_no"),
            "finished_size": document_properties.get("finished_size"),
            "remarks": document_properties.get("remarks"),
            "preview_status": document_properties.get("preview_status"),
        },
        "material": {
            "material_id": material_id,
            "material_name": material.name if material is not None else None,
            "material_version_id": document.material_version_id if document is not None else None,
            "material_version_name": material_version.name_snapshot if material_version is not None else None,
            "deform_file_name": (
                material_version.deform_file_name
                if material_version is not None and material_version.deform_file_name
                else material.deform_file_name if material is not None else None
            ),
        },
        "input_stock": {
            "geometry_type_id": _coerce_int(geometry_type_id) if geometry_type_id else None,
            "geometry_type_name": geometry_metadata.get("library_name"),
            "weight_kg": _coerce_float(document_properties.get("weight")),
            "volume_mm3": _infer_volume_mm3(document_properties),
            "attributes": attributes,
        },
        "mesh": {
            "mesh_elements": _coerce_int(document_properties.get("mesh_elements")),
        },
    }


def _document_initial_operation_properties(
    session: Session,
    *,
    document_id: int,
    document_properties: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "operation_template_id": DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
        "operation_kind": "billet",
        "target": _document_initial_target(
            session,
            document_id=document_id,
            document_properties=document_properties,
        ),
        "template_snapshot": {
            "id": DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
            "display_name": "Document initial data",
            "label": "Document initial data",
            "operation_kind": "billet",
        },
    }


def _furnace_program_table_rows(furnace_properties: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_rows = furnace_properties.get("temperature_program")
    if not isinstance(raw_rows, list):
        return []

    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(raw_rows, start=1):
        row = as_dict(raw_row)
        row_type = str(row.get("type") or "hold")
        rows.append(
            {
                "number": index,
                "type": row_type,
                "duration_min": row.get("duration_min") if row_type == "hold" else "",
                "temperature_c": row.get("temperature_c") if row_type == "hold" else "",
            }
        )
    return rows


def _furnace_operation_properties(furnace_properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "operation_template_id": FURNACE_TEMPLATE_ID,
        "operation_kind": "furnace",
        "target": {
            "temperature_program": _furnace_program_table_rows(furnace_properties),
        },
        "template_snapshot": {
            "id": FURNACE_TEMPLATE_ID,
            "display_name": "Furnace",
            "label": "Furnace",
            "operation_kind": "furnace",
        },
    }


def _coerce_decimal(value: str, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a real number") from exc


def _coerce_positive_decimal(value: str, field_name: str, *, greater_than: float = 0.0) -> float:
    parsed = _coerce_decimal(value, field_name)
    if parsed <= greater_than:
        raise ValueError(f"{field_name} must be greater than {greater_than:g}")
    return parsed


def _coerce_positive_integer(value: str, field_name: str) -> int:
    if not re.fullmatch(INTEGER_PATTERN, str(value).strip()):
        raise ValueError(f"{field_name} must be an integer")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be positive")
    return parsed


def _parse_skip_bites(value: str, num_of_bites: int) -> list[int]:
    skip_bites = [_coerce_positive_integer(item.strip(), "skip_bites item") for item in value.split(",")]
    if len(skip_bites) == 0:
        raise ValueError("skip_bites must not be empty")
    if len(skip_bites) >= num_of_bites:
        raise ValueError("skip_bites length must be less than num_of_bites")
    if max(skip_bites) > num_of_bites:
        raise ValueError("skip_bites cannot contain values greater than num_of_bites")
    return skip_bites


def _nested_value(source: Mapping[str, Any], dotted_path: str) -> Any:
    cursor: Any = source
    for part in [item for item in dotted_path.split(".") if item]:
        if not isinstance(cursor, Mapping) or part not in cursor:
            return ""
        cursor = cursor[part]
    return cursor


def normalize_right_arrow_separators(value: str) -> str:
    return RIGHT_ARROW_PATTERN.sub(STANDARD_RIGHT_ARROW, value)


def _operation_text_sentences(value: str) -> list[str]:
    normalized = normalize_right_arrow_separators(value)
    normalized = re.sub(r"[\r\n\t]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return [sentence.strip() for sentence in normalized.split(STANDARD_RIGHT_ARROW) if sentence.strip()]


def _is_initial_state_sentence(sentence: str) -> bool:
    return bool(INITIAL_STATE_RE.fullmatch(sentence))


def _height_match(sentence: str) -> re.Match[str]:
    match = HEIGHT_PATTERN_RE.fullmatch(sentence)
    if not match:
        raise ValueError(f"Unknown operation sentence format: {sentence!r}")
    return match


def _operation_props(template_id: str, target: Mapping[str, Any]) -> dict[str, Any]:
    label, operation_kind = GENERATED_OPERATION_LABELS.get(
        template_id,
        (template_id, template_id.split(".", 1)[0]),
    )
    return {
        "operation_template_id": template_id,
        "operation_template_version": 1,
        "operation_kind": operation_kind,
        "target": dict(target),
        "template_snapshot": {
            "id": template_id,
            "version": 1,
            "label": label,
            "display_name": label,
            "operation_kind": operation_kind,
        },
    }


def _parse_upsetting_sentence(
    sentence: str,
    deformation_properties: Mapping[str, Any],
) -> dict[str, Any]:
    if sentence == "0":
        return _operation_props(
            "upsetting.tail_flattening",
            {
                "rotation": 0,
                "stroke": _nested_value(deformation_properties, "deformation_variables.tail_flattening_stroke"),
            },
        )
    if sentence == "1":
        return _operation_props(
            "upsetting.tail_chamfering",
            {
                "rotation": 0,
                "stroke": _nested_value(deformation_properties, "deformation_variables.tail_chamfering_stroke"),
            },
        )

    match = _height_match(sentence)
    rotation_raw = match.group("rotation")
    height = _coerce_positive_decimal(match.group("height"), "height", greater_than=1.0)
    num_of_bites_raw = match.group("num_of_bites")
    skip_bites_raw = match.group("skip_bites")
    if skip_bites_raw:
        raise ValueError("Upsetting does not support skip_bites format")
    if num_of_bites_raw:
        if rotation_raw is not None:
            raise ValueError("Upsetting three-strokes format does not support rotation")
        num_of_bites = _coerce_positive_integer(num_of_bites_raw, "num_of_bites")
        if num_of_bites != 3:
            raise ValueError("Upsetting num_of_bites must be 3")
        return _operation_props("upsetting.three_strokes", {"rotation": 0, "height": height})

    rotation = _coerce_decimal(rotation_raw, "rotation") if rotation_raw is not None else 0
    template_id = "upsetting.rotation_height" if rotation_raw is not None else "upsetting.single_stroke"
    return _operation_props(template_id, {"rotation": rotation, "height": height})


def _parse_cogging_sentence(sentence: str) -> dict[str, Any]:
    match = _height_match(sentence)
    rotation_raw = match.group("rotation")
    height = _coerce_positive_decimal(match.group("height"), "height", greater_than=1.0)
    num_of_bites_raw = match.group("num_of_bites")
    skip_bites_raw = match.group("skip_bites")
    rotation = _coerce_decimal(rotation_raw, "rotation") if rotation_raw is not None else 0

    if skip_bites_raw:
        if not num_of_bites_raw:
            raise ValueError("skip_bites requires num_of_bites")
        num_of_bites = _coerce_positive_integer(num_of_bites_raw, "num_of_bites")
        if num_of_bites <= 1:
            raise ValueError("num_of_bites must be greater than 1 when skip_bites is used")
        return _operation_props(
            "prolongation.skip_bites",
            {
                "rotation": rotation,
                "height": height,
                "num_of_bites": num_of_bites,
                "skip_bites": _parse_skip_bites(skip_bites_raw, num_of_bites),
            },
        )

    if num_of_bites_raw:
        num_of_bites = _coerce_positive_integer(num_of_bites_raw, "num_of_bites")
        return _operation_props(
            "prolongation.height_bites",
            {"rotation": rotation, "height": height, "num_of_bites": num_of_bites},
        )

    return _operation_props("prolongation.rotation_height", {"rotation": rotation, "height": height})


def _parse_transverse_sentence(sentence: str) -> dict[str, Any]:
    match = _height_match(sentence)
    rotation_raw = match.group("rotation")
    height = _coerce_positive_decimal(match.group("height"), "height", greater_than=1.0)
    num_of_bites_raw = match.group("num_of_bites")
    skip_bites_raw = match.group("skip_bites")
    rotation = _coerce_decimal(rotation_raw, "rotation") if rotation_raw is not None else 0
    num_of_bites = _coerce_positive_integer(num_of_bites_raw, "num_of_bites") if num_of_bites_raw else 0
    skip_bites: list[int] = []

    if skip_bites_raw:
        if num_of_bites <= 1:
            raise ValueError("num_of_bites must be greater than 1 when skip_bites is used")
        skip_bites = _parse_skip_bites(skip_bites_raw, num_of_bites)

    return _operation_props(
        "transverse.all_in_one",
        {
            "rotation": rotation,
            "height": height,
            "num_of_bites": num_of_bites,
            "skip_bites": skip_bites,
        },
    )


def _parse_radial_sentence(
    sentence: str,
    deformation_properties: Mapping[str, Any],
) -> dict[str, Any]:
    radial_match = RADIAL_INITIAL_RE.fullmatch(sentence)
    if radial_match:
        return _operation_props(
            "radial.initial_rotations",
            {
                "rotation_1_x": _coerce_decimal(radial_match.group("rotation_1_x"), "rotation_1_x"),
                "rotation_2_y": _coerce_decimal(radial_match.group("rotation_2_y"), "rotation_2_y"),
                "rotation_3_x": _coerce_decimal(radial_match.group("rotation_3_x"), "rotation_3_x"),
                "rotation_4_y": _coerce_decimal(radial_match.group("rotation_4_y"), "rotation_4_y"),
            },
        )

    match = _height_match(sentence)
    rotation_raw = match.group("rotation")
    height = _coerce_positive_decimal(match.group("height"), "height", greater_than=1.0)
    num_of_bites_raw = match.group("num_of_bites")
    if match.group("skip_bites"):
        raise ValueError("Radial cogging does not support skip_bites format")
    rotation_manipulator = _coerce_decimal(rotation_raw, "rotation_manipulator") if rotation_raw is not None else 0

    if num_of_bites_raw:
        return _operation_props(
            "radial.height_bites",
            {
                "rotation_manipulator": rotation_manipulator,
                "height": height,
                "num_of_bites": _coerce_positive_integer(num_of_bites_raw, "num_of_bites"),
            },
        )

    return _operation_props(
        "radial.rotation_height_feed",
        {
            "rotation_manipulator": rotation_manipulator,
            "height": height,
        },
    )


def _parse_operation_sentence(
    sentence: str,
    *,
    selected_template_id: str,
    deformation_properties: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if selected_template_id == "operation.upsetting":
        return _parse_upsetting_sentence(sentence, deformation_properties), []
    if selected_template_id == "operation.tail_flattening":
        if sentence != "0":
            raise ValueError("Tail Flattening expects operation sentence 0")
        return _parse_upsetting_sentence(sentence, deformation_properties), []
    if selected_template_id == "operation.tail_chamfering":
        if sentence != "1":
            raise ValueError("Tail Chamfering expects operation sentence 1")
        return _parse_upsetting_sentence(sentence, deformation_properties), []
    if selected_template_id == "operation.cogging":
        return _parse_cogging_sentence(sentence), []
    if selected_template_id == "operation.transversal":
        return _parse_transverse_sentence(sentence), []
    if selected_template_id == "operation.radial":
        return _parse_radial_sentence(sentence, deformation_properties), []
    raise ValueError(f"No text parser is implemented for operation type {selected_template_id!r}")


def _rounding_rows(raw_rows: Any) -> list[Mapping[str, Any]]:
    if not isinstance(raw_rows, list):
        return []
    return [row for row in raw_rows if isinstance(row, Mapping)]


def _is_blank_rounding_row(row: Mapping[str, Any]) -> bool:
    keys = ("size", "feed", "angle", "rotations_per_feed", "speed")
    return all(str(row.get(key) or "").strip() == "" for key in keys)


def _parse_rounding_row(row: Mapping[str, Any]) -> dict[str, Any]:
    final_diameter = _coerce_positive_decimal(str(row.get("size") or "").strip(), "Size")
    feed = _coerce_positive_decimal(str(row.get("feed") or "").strip(), "Feed")
    angle = _coerce_decimal(str(row.get("angle") or "").strip(), "Angle")
    rotations_per_feed = _coerce_positive_integer(str(row.get("rotations_per_feed") or "").strip(), "Rotations per Feed")
    speed = _coerce_positive_decimal(str(row.get("speed") or "").strip(), "Speed")
    template_id = (
        "rounding.spiral_one_rotation"
        if rotations_per_feed == 1
        else "rounding.spiral_three_rotations"
    )
    return _operation_props(
        template_id,
        {
            "final_diameter": final_diameter,
            "feed": feed,
            "angle": angle,
            "rotations_per_feed": rotations_per_feed,
            "speed": speed,
            # Current preprocessor still consumes these canonical names.
            "diameter": final_diameter,
            "rotation_per_bite": angle,
        },
    )


def _feed_settings_key_for_template(template_id: str | None) -> str | None:
    if not template_id:
        return None
    if template_id == "upsetting.tail_flattening":
        return "tail_flattening"
    if template_id.startswith("prolongation."):
        return "cogging"
    if template_id in {
        "radial.rotation_height_feed",
        "radial.height_bites",
        "radial.press_axis_feed",
    }:
        return "radial"
    if template_id.startswith("transverse.") or template_id.startswith("transversal."):
        return "transversal"
    return None


def _template_requires_deformation_feed(template_id: str | None) -> bool:
    return template_id in {
        "prolongation.rotation_height",
        "radial.rotation_height_feed",
        "transverse.all_in_one",
        "transversal.rotation_height",
    }


def _speed_field_for_template(template_id: str | None) -> str | None:
    if not template_id:
        return None
    if template_id in {
        "upsetting.rotation_height",
        "upsetting.single_stroke",
        "upsetting.three_strokes",
    }:
        return DEFORMATION_UPSETTING_SPEED_FIELD
    if template_id.startswith("rounding.") or template_id == "radial.initial_rotations":
        return None
    if template_id.startswith(
        (
            "upsetting.",
            "prolongation.",
            "radial.",
            "transverse.",
            "transversal.",
            "cutting.",
        )
    ):
        return DEFORMATION_PROLONGATION_SPEED_FIELD
    return None


def _coerce_feed_direction_id(value: Any) -> int:
    if value in (None, ""):
        return FEED_DIRECTION_DEFAULT_ID
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{FEED_DIRECTION_FIELD} must be one of 2 (-->) / 3 (<--) / 4 (<->)") from exc
    if parsed not in FEED_DIRECTION_ALLOWED_IDS:
        raise ValueError(f"{FEED_DIRECTION_FIELD} must be one of 2 (-->) / 3 (<--) / 4 (<->)")
    return parsed


def _coerce_optional_feed_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text == "":
        return None
    return _coerce_positive_decimal(text, "feed")


def _deformation_feed_settings(
    deformation_properties: Mapping[str, Any],
    settings_key: str,
) -> dict[str, Any]:
    settings_root = as_dict(deformation_properties.get(FEED_SETTINGS_KEY))
    settings = as_dict(settings_root.get(settings_key))
    result: dict[str, Any] = {
        FEED_DIRECTION_FIELD: _coerce_feed_direction_id(settings.get(FEED_DIRECTION_FIELD)),
    }
    for field in FEED_VALUE_FIELDS:
        value = _coerce_optional_feed_value(settings.get(field))
        if value is not None:
            result[field] = value
    return result


def _copy_deformation_parameters(
    operation_parameters: Mapping[str, Any],
    deformation_properties: Mapping[str, Any],
    template_id: str | None,
) -> dict[str, Any]:
    result = deepcopy(dict(operation_parameters))

    for field in DEFORMATION_DIE_PARAMETER_FIELDS:
        value = deformation_properties.get(field)
        if value not in (None, ""):
            result[field] = value

    speed_field = _speed_field_for_template(template_id)
    if speed_field is not None:
        value = deformation_properties.get(speed_field)
        if value not in (None, ""):
            result[speed_field] = value

    settings_key = _feed_settings_key_for_template(template_id)
    if settings_key is None:
        return result

    feed_settings = _deformation_feed_settings(deformation_properties, settings_key)
    requires_feed = _template_requires_deformation_feed(template_id)
    if requires_feed and "feed_first" not in feed_settings:
        raise ValueError(
            f"{template_id} requires explicit positive {FEED_SETTINGS_KEY}.{settings_key}.feed_first [mm]"
        )

    result.update(feed_settings)
    return result


def _operation_parameters_from_payload(operation_payload: Mapping[str, Any]) -> dict[str, Any]:
    target = operation_payload.get("target")
    return deepcopy(dict(target)) if isinstance(target, Mapping) else {}


def _delete_existing(session: Session, document_id: int) -> None:
    existing = session.scalars(
        select(DocumentOperation).where(DocumentOperation.document_id == document_id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()


def _operation_snapshot_label(
    *,
    template_id: str | None,
    operation_kind: str,
    label_snapshot: str | None,
    source_block_type_id: str,
) -> str:
    return label_snapshot or template_id or operation_kind or source_block_type_id


def _add_simulation_step_sibling(
    session: Session,
    *,
    document_version: DocumentVersion,
    operation_row: DocumentOperation,
) -> None:
    is_preprocess_ready = (
        operation_row.parse_status == "valid"
        and operation_row.operation_template_id not in (None, "")
    )
    snapshot_label = _operation_snapshot_label(
        template_id=operation_row.operation_template_id,
        operation_kind=operation_row.operation_kind,
        label_snapshot=operation_row.label_snapshot,
        source_block_type_id=operation_row.source_block_type_id,
    )
    document = document_version.document
    simulation_step = SimulationStep(
        document_operation_id=operation_row.document_operation_id,
        document_version_id=document_version.document_version_id,
        execution_order=operation_row.operation_order,
        source_block_id=operation_row.source_block_id,
        operation_template_id=operation_row.operation_template_id,
        operation_kind=operation_row.operation_kind,
        operation_label_snapshot=operation_row.label_snapshot,
        preprocess_ready=is_preprocess_ready,
        block_name_snapshot=snapshot_label,
        library_name_snapshot=snapshot_label,
        material_version_id=document.material_version_id if document is not None else None,
        parameter_values={},
        control_parameters={},
        step_specific_parameters={},
        metrics={},
    )
    session.add(simulation_step)
    if is_preprocess_ready:
        session.add(
            SimulationStepStatus(
                document_operation_id=operation_row.document_operation_id,
                status=SimulationStepStatusEnum.blocked,
            )
        )


def _add_operation_row(
    session: Session,
    *,
    document_version: DocumentVersion,
    document_id: int,
    source_block_id: Any,
    operation_order: int,
    operation_order_in_block: int,
    source_block_type_id: str,
    operation_properties: Mapping[str, Any],
    deformation_properties: Mapping[str, Any],
    source_text_hash: str | None = None,
    parse_status: str = "valid",
    parse_errors: list[dict[str, Any]] | None = None,
    parse_warnings: list[dict[str, Any]] | None = None,
) -> None:
    template_id = operation_properties.get("operation_template_id")
    operation_kind = _operation_kind_from_template(str(template_id) if template_id else None, operation_properties)
    template_snapshot = as_dict(operation_properties.get("template_snapshot"))
    operation_parameters = _operation_parameters_from_payload(operation_properties)
    if source_block_type_id == OPERATION_BLOCK_TYPE_ID:
        operation_parameters = _copy_deformation_parameters(
            operation_parameters,
            deformation_properties,
            str(template_id) if template_id else None,
        )

    operation_row = DocumentOperation(
        document_id=document_id,
        source_block_id=source_block_id,
        operation_order=operation_order,
        operation_order_in_block=operation_order_in_block,
        source_block_type_id=source_block_type_id,
        operation_template_id=str(template_id) if template_id else None,
        operation_kind=operation_kind,
        label_snapshot=_operation_label(operation_properties),
        operation_parameters=operation_parameters,
        template_snapshot=template_snapshot,
        source_text_hash=source_text_hash,
        parse_status=parse_status,
        parse_errors=parse_errors or [],
        parse_warnings=parse_warnings or [],
    )
    session.add(operation_row)
    session.flush()
    _add_simulation_step_sibling(session, document_version=document_version, operation_row=operation_row)


def regenerate_document_operations(session: Session, document_id: int) -> int:
    """Rebuild materialized operation rows from explicit block props.

    `document_blocks.props` remains the explicit user-authored source. Parent
    deformation parameters are copied into each generated operation row here.
    """

    document_version = _latest_document_version(session, document_id)
    if document_version is None:
        raise ValueError(
            f"Cannot regenerate document operations for document_id={document_id}: document version does not exist"
        )

    _delete_existing(session, document_id)

    document_properties: dict[str, Any] = {}
    current_section_type: str | None = None
    current_deformation_properties: dict[str, Any] = {}
    operation_order = 1

    for block in _ordered_blocks(session, document_id):
        normalized_props = normalize_props_for_block_type(block.block_type_id, block.props)

        if block.block_type_id == DOCUMENT_BLOCK_TYPE_ID:
            document_properties = deep_merge(
                document_properties,
                extract_namespace(normalized_props, DOCUMENT_PROPERTIES),
            )
            _add_operation_row(
                session,
                document_version=document_version,
                document_id=document_id,
                source_block_id=block.block_id,
                operation_order=operation_order,
                operation_order_in_block=0,
                source_block_type_id=DOCUMENT_BLOCK_TYPE_ID,
                operation_properties=_document_initial_operation_properties(
                    session,
                    document_id=document_id,
                    document_properties=document_properties,
                ),
                deformation_properties={},
            )
            operation_order += 1
            current_section_type = None
            current_deformation_properties = {}
            continue

        if block.block_type_id == HEATING_BLOCK_TYPE_ID:
            current_section_type = HEATING_BLOCK_TYPE_ID
            current_deformation_properties = {}
            continue

        if block.block_type_id == DEFORMATION_BLOCK_TYPE_ID:
            current_section_type = DEFORMATION_BLOCK_TYPE_ID
            current_deformation_properties = extract_namespace(normalized_props, DEFORMATION_PROPERTIES)
            continue

        if block.block_type_id == FURNACE_BLOCK_TYPE_ID:
            furnace_properties = extract_namespace(normalized_props, FURNACE_PROPERTIES)
            _add_operation_row(
                session,
                document_version=document_version,
                document_id=document_id,
                source_block_id=block.block_id,
                operation_order=operation_order,
                operation_order_in_block=0,
                source_block_type_id=FURNACE_BLOCK_TYPE_ID,
                operation_properties=_furnace_operation_properties(furnace_properties),
                deformation_properties={},
            )
            operation_order += 1
            continue

        if block.block_type_id == OPERATION_BLOCK_TYPE_ID:
            direct_deformation_properties = (
                current_deformation_properties
                if current_section_type == DEFORMATION_BLOCK_TYPE_ID
                else {}
            )
            operation_properties = extract_namespace(normalized_props, OPERATION_PROPERTIES)
            selected_template_id = str(operation_properties.get("operation_template_id") or "")
            is_parser_backed_operation = selected_template_id in PARSER_OPERATION_BLOCK_TEMPLATE_IDS
            operation_text = str(operation_properties.get("operation_text") or "")

            if selected_template_id == "operation.rounding":
                parsed_rounding_rows = 0
                for row_index, row in enumerate(_rounding_rows(operation_properties.get("rounding_table")), start=1):
                    if _is_blank_rounding_row(row):
                        continue
                    parsed_rounding_rows += 1
                    source_text_hash = hashlib.sha256(
                        json.dumps(dict(row), sort_keys=True, ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                    try:
                        parsed_operation_properties = _parse_rounding_row(row)
                        parsed_operation_properties["rounding_table"] = operation_properties.get("rounding_table")
                        _add_operation_row(
                            session,
                            document_version=document_version,
                            document_id=document_id,
                            source_block_id=block.block_id,
                            operation_order=operation_order,
                            operation_order_in_block=row_index,
                            source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                            operation_properties=parsed_operation_properties,
                            deformation_properties=direct_deformation_properties,
                            source_text_hash=source_text_hash,
                        )
                    except Exception as exc:
                        _add_operation_row(
                            session,
                            document_version=document_version,
                            document_id=document_id,
                            source_block_id=block.block_id,
                            operation_order=operation_order,
                            operation_order_in_block=row_index,
                            source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                            operation_properties={
                                "operation_template_id": None,
                                "operation_kind": "parse_error",
                                "rounding_table": operation_properties.get("rounding_table"),
                                "source_row": dict(row),
                                "template_snapshot": {},
                            },
                            deformation_properties=direct_deformation_properties,
                            source_text_hash=source_text_hash,
                            parse_status="error",
                            parse_errors=[
                                {
                                    "row": row_index,
                                    "source_row": dict(row),
                                    "message": str(exc),
                                }
                            ],
                        )
                    operation_order += 1
                if parsed_rounding_rows > 0:
                    continue

            sentences = _operation_text_sentences(operation_text)
            parsed_text_sentences = 0
            for sentence_index, sentence in enumerate(sentences, start=1):
                if _is_initial_state_sentence(sentence):
                    if sentence_index == 1:
                        continue
                    source_text_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
                    _add_operation_row(
                        session,
                        document_version=document_version,
                        document_id=document_id,
                        source_block_id=block.block_id,
                        operation_order=operation_order,
                        operation_order_in_block=sentence_index,
                        source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                        operation_properties={
                            "operation_template_id": None,
                            "operation_kind": "parse_error",
                            "operation_text": operation_text,
                            "source_sentence": sentence,
                            "template_snapshot": {},
                        },
                        deformation_properties=direct_deformation_properties,
                        source_text_hash=source_text_hash,
                        parse_status="error",
                        parse_errors=[
                            {
                                "sentence": sentence_index,
                                "source_sentence": sentence,
                                "message": "Initial state is allowed only in first position",
                            }
                        ],
                    )
                    operation_order += 1
                    parsed_text_sentences += 1
                    continue

                parsed_text_sentences += 1
                source_text_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
                try:
                    parsed_operation_properties, parse_warnings = _parse_operation_sentence(
                        sentence,
                        selected_template_id=selected_template_id,
                        deformation_properties=direct_deformation_properties,
                    )
                    parsed_operation_properties["operation_text"] = operation_text
                    parsed_operation_properties["source_sentence"] = sentence
                    _add_operation_row(
                        session,
                        document_version=document_version,
                        document_id=document_id,
                        source_block_id=block.block_id,
                        operation_order=operation_order,
                        operation_order_in_block=sentence_index,
                        source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                        operation_properties=parsed_operation_properties,
                        deformation_properties=direct_deformation_properties,
                        source_text_hash=source_text_hash,
                        parse_warnings=parse_warnings,
                    )
                except Exception as exc:
                    _add_operation_row(
                        session,
                        document_version=document_version,
                        document_id=document_id,
                        source_block_id=block.block_id,
                        operation_order=operation_order,
                        operation_order_in_block=sentence_index,
                        source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                        operation_properties={
                            "operation_template_id": None,
                            "operation_kind": "parse_error",
                            "operation_text": operation_text,
                            "source_sentence": sentence,
                            "template_snapshot": {},
                        },
                        deformation_properties=direct_deformation_properties,
                        source_text_hash=source_text_hash,
                        parse_status="error",
                        parse_errors=[
                            {
                                "sentence": sentence_index,
                                "source_sentence": sentence,
                                "message": str(exc),
                            }
                        ],
                    )
                operation_order += 1
            if parsed_text_sentences > 0:
                continue

            template_id = operation_properties.get("operation_template_id")
            if not template_id or str(template_id) == EMPTY_OPERATION_TEMPLATE_ID:
                continue
            if is_parser_backed_operation:
                continue

            _add_operation_row(
                session,
                document_version=document_version,
                document_id=document_id,
                source_block_id=block.block_id,
                operation_order=operation_order,
                operation_order_in_block=0,
                source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                operation_properties=operation_properties,
                deformation_properties=direct_deformation_properties,
            )
            operation_order += 1

    session.flush()
    return operation_order - 1

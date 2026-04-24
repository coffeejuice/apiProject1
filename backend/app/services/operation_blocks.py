"""Generic document block support backed by ``document_blocks_library``."""

from __future__ import annotations

from collections.abc import Mapping
import re
from string import Formatter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library.library import OperationsLibrary


TRANSIENT_OPERATION_PROP_KEYS = frozenset(
    {
        "title",
        "operation_type",
        "editable_fields",
        "field_limits",
    }
)

FIXED_SYSTEM_OPERATION_TYPE_IDS = frozenset({5, 84})
DEFORMATION_BUNDLE_LEADER_TYPE_ID = 24
DEFORMATION_BUNDLE_MEMBER_TYPE_IDS = frozenset()
FEED_DIRECTION_DEFAULT_ID = 3
FEED_DIRECTION_FIELD_NAMES = frozenset(
    {
        "feed_direction_id",
        "feed_direction_upsetting_id",
        "feed_direction_prolongation_id",
        "feed_direction_transversal_cogging_id",
    }
)
FEED_DIRECTION_OPTIONS = (
    {"value": "3", "label": "<--"},
    {"value": "4", "label": "<->"},
    {"value": "2", "label": "-->"},
)


def coerce_operation_type_id(block_type_id: object) -> int | None:
    if block_type_id is None:
        return None
    text = str(block_type_id).strip()
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def strip_legacy_language_prefix(value: str | None) -> str:
    if value is None:
        return ""

    parts = str(value).split("|")
    if len(parts) >= 3 and parts[0] == "LANGUAGE":
        return "|".join(parts[2:])
    return str(value)


def split_legacy_pipe_string(value: str | None) -> list[str]:
    normalized = strip_legacy_language_prefix(value)
    if not normalized:
        return []
    return [part.strip() for part in normalized.split("|") if part.strip()]


def _localized_name(value: object) -> str:
    if isinstance(value, Mapping):
        for key in ("EN", "en", "RU", "ru", "ZH_HANS", "zh_hans"):
            option = value.get(key)
            if option:
                return str(option)
        for option in value.values():
            if option:
                return str(option)
        return ""
    return "" if value is None else str(value)


def get_operation_type(db: Session, block_type_id: object) -> OperationsLibrary | None:
    type_id = coerce_operation_type_id(block_type_id)
    if type_id is None:
        return None
    return db.execute(
        select(OperationsLibrary).where(OperationsLibrary.type_id == type_id)
    ).scalars().first()


def is_operation_block_type(db: Session, block_type_id: object) -> bool:
    operation = get_operation_type(db, block_type_id)
    return operation is not None and not operation.is_obsolete


def operation_has_children(db: Session, block_type_id: object) -> bool:
    type_id = coerce_operation_type_id(block_type_id)
    if type_id is None:
        return False
    child_type_id = db.execute(
        select(OperationsLibrary.type_id)
        .where(OperationsLibrary.parent_type_id == type_id)
        .limit(1)
    ).scalar()
    return child_type_id is not None


def is_insertable_operation_block_type(db: Session, block_type_id: object) -> bool:
    type_id = coerce_operation_type_id(block_type_id)
    if type_id == DEFORMATION_BUNDLE_LEADER_TYPE_ID:
        return is_operation_block_type(db, block_type_id)
    if type_id in DEFORMATION_BUNDLE_MEMBER_TYPE_IDS:
        return False
    return (
        type_id not in FIXED_SYSTEM_OPERATION_TYPE_IDS
        and is_operation_block_type(db, block_type_id)
        and not operation_has_children(db, block_type_id)
    )


def operation_columns(operation: OperationsLibrary) -> list[str]:
    return split_legacy_pipe_string(operation.db_column_names)


def operation_labels(operation: OperationsLibrary) -> list[str]:
    labels = split_legacy_pipe_string(operation.labels)
    columns = operation_columns(operation)
    if len(labels) >= len(columns):
        return labels
    return labels + columns[len(labels):]


def sanitize_operation_props(db: Session, block_type_id: object, props: Mapping[str, Any] | None) -> dict[str, Any]:
    operation = get_operation_type(db, block_type_id)
    if operation is None:
        return dict(props or {})

    raw_props = dict(props or {})
    columns = set(operation_columns(operation))
    sanitized = {
        key: value
        for key, value in raw_props.items()
        if key in columns and key not in TRANSIENT_OPERATION_PROP_KEYS
    }
    return _apply_required_operation_defaults(db, operation, sanitized)


def build_default_operation_props(
    db: Session,
    block_type_id: object,
    props: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    operation = get_operation_type(db, block_type_id)
    if operation is None:
        return dict(props or {})

    supplied = sanitize_operation_props(db, block_type_id, props)
    defaults = _required_operation_defaults(db, operation)
    return {
        column: supplied.get(column) or defaults.get(column, "")
        for column in operation_columns(operation)
    }


def _required_operation_defaults(db: Session, operation: OperationsLibrary) -> dict[str, object]:
    defaults: dict[str, object] = {}
    columns = operation_columns(operation)
    if "press_id" in columns:
        default_press_id = _get_default_press_id(db)
        if default_press_id is not None:
            defaults["press_id"] = default_press_id
    for column in columns:
        if column in FEED_DIRECTION_FIELD_NAMES:
            defaults[column] = FEED_DIRECTION_DEFAULT_ID
    return defaults


def _apply_required_operation_defaults(
    db: Session,
    operation: OperationsLibrary,
    props: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = dict(props)
    for key, value in _required_operation_defaults(db, operation).items():
        if normalized.get(key) in (None, ""):
            normalized[key] = value
    if "press_id" in operation_columns(operation) and normalized.get("press_id") not in (None, ""):
        press_id = _coerce_int(normalized.get("press_id"))
        if press_id is None or not _is_active_press_id(db, press_id):
            raise ValueError("press_id must reference one active press")
    return normalized


def _get_default_press_id(db: Session) -> int | None:
    from app.models.library.press import Press

    return db.execute(
        select(Press.id)
        .where(Press.is_obsolete.is_(False))
        .order_by(Press.id.asc())
        .limit(1)
    ).scalar()


def _is_active_press_id(db: Session, press_id: int) -> bool:
    from app.models.library.press import Press

    return db.execute(
        select(Press.id)
        .where(Press.id == press_id, Press.is_obsolete.is_(False))
        .limit(1)
    ).scalar() is not None


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def generate_operation_title(operation: OperationsLibrary, props: Mapping[str, Any] | None) -> str:
    process_name = strip_legacy_language_prefix(operation.process_name)
    if not process_name:
        process_name = strip_legacy_language_prefix(operation.library_name)

    columns = operation_columns(operation)
    values = []
    for column in columns:
        value = (props or {}).get(column)
        values.append("_" if value is None or value == "" else str(value))

    formatter = Formatter()
    field_count = sum(1 for _, field_name, _, _ in formatter.parse(process_name) if field_name is not None)
    if field_count > len(values):
        values.extend(["_"] * (field_count - len(values)))

    try:
        return process_name.format(*values)
    except (IndexError, KeyError, ValueError):
        return strip_legacy_language_prefix(operation.library_name) or f"Operation {operation.type_id}"


def operation_type_to_payload(operation: OperationsLibrary, *, has_children: bool = False) -> dict[str, Any]:
    columns = operation_columns(operation)
    insertable = (
        not operation.is_obsolete
        and (
            operation.type_id == DEFORMATION_BUNDLE_LEADER_TYPE_ID
            or (
                operation.type_id not in FIXED_SYSTEM_OPERATION_TYPE_IDS
                and operation.type_id not in DEFORMATION_BUNDLE_MEMBER_TYPE_IDS
                and not has_children
            )
        )
    )
    return {
        "type_id": operation.type_id,
        "parent_type_id": operation.parent_type_id,
        "row": operation.row,
        "process_fixed_row": operation.process_fixed_row,
        "allow_copies": operation.allow_copies,
        "text_id": operation.text_id,
        "library_name": strip_legacy_language_prefix(operation.library_name),
        "process_name": strip_legacy_language_prefix(operation.process_name),
        "labels": operation_labels(operation),
        "db_column_names": columns,
        "foreign_keys": split_legacy_pipe_string(operation.foreign_keys),
        "is_simulation": operation.is_simulation,
        "is_geometry": operation.is_geometry,
        "is_die_assembly": operation.is_die_assembly,
        "is_custom_die_assembly": operation.is_custom_die_assembly,
        "is_press": operation.is_press,
        "is_feed": operation.is_feed,
        "is_top_die": operation.is_top_die,
        "is_bottom_die": operation.is_bottom_die,
        "is_speed": operation.is_speed,
        "is_billet_category": operation.is_billet_category,
        "is_heating_category": operation.is_heating_category,
        "is_forming_category": operation.is_forming_category,
        "is_forming_operation": operation.is_forming_operation,
        "is_surface_treatment_operation": operation.is_surface_treatment_operation,
        "deformation_type": operation.deformation_type,
        "speed_column_name": operation.speed_column_name,
        "trigger": operation.trigger,
        "is_initialize": operation.is_initialize,
        "is_accumulate": operation.is_accumulate,
        "is_keep": operation.is_keep,
        "is_obsolete": operation.is_obsolete,
        "has_children": has_children,
        "insertable": insertable,
    }


def operation_field_options(db: Session, operation: OperationsLibrary) -> dict[str, list[dict[str, str]]]:
    columns = operation_columns(operation)
    options: dict[str, list[dict[str, str]]] = {}
    if "press_id" in columns:
        from app.models.library.press import Press

        presses = db.execute(
            select(Press)
            .where(Press.is_obsolete.is_(False))
            .order_by(Press.id.asc())
        ).scalars().all()
        options["press_id"] = [
            {"value": str(press.id), "label": _localized_name(press.name) or f"Press {press.id}"}
            for press in presses
        ]
    for column in columns:
        if column in FEED_DIRECTION_FIELD_NAMES:
            options[column] = [dict(option) for option in FEED_DIRECTION_OPTIONS]
    return options


def serialize_operation_block_for_frontend(
    db: Session,
    block_type_id: object,
    props: Mapping[str, Any] | None,
) -> dict[str, Any]:
    operation = get_operation_type(db, block_type_id)
    if operation is None:
        return dict(props or {})

    persisted_props = build_default_operation_props(db, block_type_id, props)
    operation_type = operation_type_to_payload(operation)
    field_options = operation_field_options(db, operation)
    if field_options:
        operation_type["field_options"] = field_options
    return {
        **persisted_props,
        "title": generate_operation_title(operation, persisted_props),
        "operation_type": operation_type,
    }


def get_operation_field_limits(db: Session, block_type_id: object) -> dict[str, int] | None:
    operation = get_operation_type(db, block_type_id)
    if operation is None:
        return None
    return {column: 255 for column in operation_columns(operation)}

"""Semantic Operation block support for the editor-facing Operation block."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.services.block_props import (
    OPERATION_PROPERTIES,
    extract_namespace,
    normalize_operation_block_props,
)

OPERATION_BLOCK_TYPE_ID = "operation"
DEFAULT_OPERATION_TEMPLATE_ID = "operation.empty"
PARAMETERS_CALCULATION_MODE_SELECTOR: dict[str, Any] = {
    "target_path": "target.parameters_calculation_mode",
    "allow_none": False,
    "default": "manual",
    "tree": [
        {"id": "manual", "label": "Manual", "value": "manual"},
        {"id": "auto", "label": "Auto", "value": "auto"},
        {"id": "optimization", "label": "Optimization", "value": "optimization"},
    ],
}
OPERATION_TYPE_SELECTOR: dict[str, Any] = {
    "target_path": "operation_template_id",
    "display_name_key": "display_name",
    "allow_none": True,
    "default_template_id": DEFAULT_OPERATION_TEMPLATE_ID,
    "tree": [
        {"id": "operation.upsetting", "label": "Upsetting", "template_id": "operation.upsetting"},
        {"id": "operation.tail_flattening", "label": "Tail Flattening", "template_id": "operation.tail_flattening"},
        {"id": "operation.tail_chamfering", "label": "Tail Chamfering", "template_id": "operation.tail_chamfering"},
        {"id": "operation.cogging", "label": "Cogging", "template_id": "operation.cogging"},
        {"id": "operation.rounding", "label": "Rounding", "template_id": "operation.rounding"},
        {"id": "operation.radial", "label": "Radial Cogging", "template_id": "operation.radial"},
        {"id": "operation.transversal", "label": "Transverse Cogging", "template_id": "operation.transversal"},
        {"id": "operation.cut", "label": "Cutting", "template_id": "operation.cut"},
    ],
}
OPERATION_BLOCK_PARSING_RULES: dict[str, dict[str, str]] = {
    "operation.upsetting": {
        "mode": "arrow_sentences",
        "description": (
            "Operation text is parsed as right-arrow-separated sentences. "
            "Newlines, tabs, and repeated spaces are visual formatting only."
        ),
    },
    "operation.tail_flattening": {
        "mode": "arrow_sentences",
        "description": "Tail flattening text parser accepts the legend sentence 0.",
    },
    "operation.tail_chamfering": {
        "mode": "arrow_sentences",
        "description": "Tail chamfering text parser accepts the legend sentence 1.",
    },
    "operation.cogging": {
        "mode": "arrow_sentences",
        "description": "Cogging text is parsed as right-arrow-separated height/rotation/bite sentences.",
    },
    "operation.radial": {
        "mode": "arrow_sentences",
        "description": "Radial cogging text is parsed as right-arrow-separated XYXY or height/rotation/bite sentences.",
    },
    "operation.transversal": {
        "mode": "arrow_sentences",
        "description": "Transverse cogging text is parsed as right-arrow-separated height/rotation/bite sentences.",
    },
    "operation.cut": {
        "mode": "arrow_sentences",
        "description": "Cutting text input is reserved; current parser emits parse errors until formats are defined.",
    },
    "operation.rounding": {
        "mode": "rounding_table",
        "description": "Rounding is parsed from table rows; one non-empty row creates one operation.",
    },
}
_ROUNDING_INPUT_SCHEMA: list[dict[str, Any]] = [
    {"key": "pass", "label": "Pass", "type": "auto_integer"},
    {"key": "size", "label": "Size", "type": "positive_decimal", "unit": "mm"},
    {"key": "feed", "label": "Feed", "type": "positive_decimal", "unit": "mm"},
    {"key": "angle", "label": "Angle", "type": "decimal", "unit": "deg"},
    {"key": "rotations_per_feed", "label": "Rotations per Feed", "type": "positive_integer"},
    {"key": "speed", "label": "Speed", "type": "positive_decimal", "unit": "mm/s"},
]
_OPERATION_BLOCK_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "id": DEFAULT_OPERATION_TEMPLATE_ID,
        "version": 1,
        "label": "Empty operation",
        "display_name": "Empty operation",
        "category": "generic",
        "operation_kind": "empty",
        "compiler_handler": "noop",
        "insertable": False,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.upsetting",
        "version": 1,
        "label": "Upsetting",
        "display_name": "Upsetting",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.tail_flattening",
        "version": 1,
        "label": "Tail Flattening",
        "display_name": "Tail Flattening",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.tail_chamfering",
        "version": 1,
        "label": "Tail Chamfering",
        "display_name": "Tail Chamfering",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.cogging",
        "version": 1,
        "label": "Cogging",
        "display_name": "Cogging",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.rounding",
        "version": 1,
        "label": "Rounding",
        "display_name": "Rounding",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "rounding_table",
        "input_schema": _ROUNDING_INPUT_SCHEMA,
        "target_schema": [],
    },
    {
        "id": "operation.radial",
        "version": 1,
        "label": "Radial Cogging",
        "display_name": "Radial Cogging",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.transversal",
        "version": 1,
        "label": "Transverse Cogging",
        "display_name": "Transverse Cogging",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
    {
        "id": "operation.cut",
        "version": 1,
        "label": "Cutting",
        "display_name": "Cutting",
        "category": "operation_block",
        "operation_kind": "operation_block",
        "compiler_handler": "operation_block_parser",
        "insertable": True,
        "materialize": False,
        "input_method": "text",
        "input_schema": [],
        "target_schema": [],
    },
)
TRANSIENT_OPERATION_PROP_KEYS = frozenset(
    {
        "title",
        "operation_template",
        "operation_type",
        "operation_templates",
        "operation_type_selector",
        "operation_block_parsing_rules",
        "parameters_calculation_mode_selector",
        "editable_fields",
        "field_limits",
    }
)


def _as_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, Mapping)]


def _set_nested(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        return

    cursor = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def _get_nested(source: Mapping[str, Any], dotted_path: str) -> Any:
    cursor: Any = source
    for part in [part for part in dotted_path.split(".") if part]:
        if not isinstance(cursor, Mapping) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def list_operation_templates(*, insertable_only: bool = False) -> list[dict[str, Any]]:
    templates = [dict(template) for template in _OPERATION_BLOCK_TEMPLATES]
    if insertable_only:
        return [template for template in templates if template.get("insertable", True)]
    return templates


def get_operation_template(template_id: str | None) -> dict[str, Any]:
    resolved_id = template_id or DEFAULT_OPERATION_TEMPLATE_ID
    for template in _OPERATION_BLOCK_TEMPLATES:
        if template["id"] == resolved_id:
            return dict(template)
    raise KeyError(f"Unknown operation block template: {resolved_id}")


def _build_target_defaults(template: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    calculation_path = str(PARAMETERS_CALCULATION_MODE_SELECTOR.get("target_path") or "")
    if calculation_path.startswith("target."):
        _set_nested(
            result,
            calculation_path.removeprefix("target."),
            PARAMETERS_CALCULATION_MODE_SELECTOR.get("default", "manual"),
        )
    for field in _as_list(template.get("target_schema")):
        path = str(field.get("path") or "")
        if path.startswith("target."):
            _set_nested(result, path.removeprefix("target."), field.get("default", ""))
    return result


def _merge_target_values(target: dict[str, Any], overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(overrides, Mapping):
        return target
    merged = dict(target)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_target_values(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_operation_props(
    template_id: str | None = None,
    props: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw_props = dict(props or {})
    resolved_template_id = str(raw_props.get("operation_template_id") or template_id or DEFAULT_OPERATION_TEMPLATE_ID)
    template = get_operation_template(resolved_template_id)
    target = _merge_target_values(_build_target_defaults(template), raw_props.get("target"))

    return {
        "operation_template_id": template["id"],
        "operation_template_version": template["version"],
        "operation_kind": template["operation_kind"],
        "operation_text": str(raw_props.get("operation_text") or ""),
        "rounding_table": raw_props.get("rounding_table") if isinstance(raw_props.get("rounding_table"), list) else [],
        "target": target,
        "template_snapshot": template,
    }


def _sanitize_editor_operation_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw_props = dict(props or {})
    return build_operation_props(
        str(raw_props.get("operation_template_id") or DEFAULT_OPERATION_TEMPLATE_ID),
        raw_props,
    )


def _serialize_editor_operation_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    sanitized = _sanitize_editor_operation_props(props)
    template = get_operation_template(str(sanitized.get("operation_template_id") or DEFAULT_OPERATION_TEMPLATE_ID))
    return {
        **sanitized,
        "title": template.get("display_name") or template["label"],
        "operation_template": template,
        "operation_templates": list_operation_templates(),
        "operation_type_selector": OPERATION_TYPE_SELECTOR,
        "operation_block_parsing_rules": OPERATION_BLOCK_PARSING_RULES,
        "parameters_calculation_mode_selector": PARAMETERS_CALCULATION_MODE_SELECTOR,
    }


def _flatten_operation_target(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw_props = dict(props or {})
    target = raw_props.get("target")
    if not isinstance(target, Mapping):
        return {}

    template: Mapping[str, Any] = (
        raw_props.get("template_snapshot")
        if isinstance(raw_props.get("template_snapshot"), Mapping)
        else {}
    )
    if not template:
        template_id = raw_props.get("operation_template_id")
        if template_id:
            try:
                template = get_operation_template(str(template_id))
            except KeyError:
                template = {}

    flattened: dict[str, Any] = {}
    for field in _as_list(template.get("target_schema")):
        path = str(field.get("path") or "")
        if not path.startswith("target."):
            continue
        key = path.removeprefix("target.")
        flattened[key] = _get_nested(target, key)
    return flattened


def is_operation_block_type(db: Session, block_type_id: object) -> bool:
    return str(block_type_id) == OPERATION_BLOCK_TYPE_ID


def is_insertable_operation_block_type(db: Session, block_type_id: object) -> bool:
    return is_operation_block_type(db, block_type_id)


def sanitize_operation_props(
    db: Session,
    block_type_id: object,
    props: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not is_operation_block_type(db, block_type_id):
        return dict(props or {})

    normalized = normalize_operation_block_props(props)
    raw_props = {
        key: value
        for key, value in extract_namespace(normalized, OPERATION_PROPERTIES).items()
        if key not in TRANSIENT_OPERATION_PROP_KEYS
    }
    return {OPERATION_PROPERTIES: _sanitize_editor_operation_props(raw_props)}


def build_default_operation_props(
    db: Session,
    block_type_id: object,
    props: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not is_operation_block_type(db, block_type_id):
        return dict(props or {})
    normalized = normalize_operation_block_props(props)
    operation_props = extract_namespace(normalized, OPERATION_PROPERTIES)
    return {OPERATION_PROPERTIES: build_operation_props(props=operation_props)}


def serialize_operation_block_for_frontend(
    db: Session,
    block_type_id: object,
    props: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not is_operation_block_type(db, block_type_id):
        return dict(props or {})
    normalized = normalize_operation_block_props(props)
    operation_props = extract_namespace(normalized, OPERATION_PROPERTIES)
    return {
        **normalized,
        **_serialize_editor_operation_props(operation_props),
    }


def get_operation_field_limits(db: Session, block_type_id: object) -> dict[str, int] | None:
    if not is_operation_block_type(db, block_type_id):
        return None
    return {
        "operation_template_id": 255,
        "operation_text": 12000,
        f"{OPERATION_PROPERTIES}.operation_text": 12000,
        f"{OPERATION_PROPERTIES}.rounding_table": 12000,
    }


def operation_target_to_parameters(props: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_operation_block_props(props)
    return _flatten_operation_target(extract_namespace(normalized, OPERATION_PROPERTIES))

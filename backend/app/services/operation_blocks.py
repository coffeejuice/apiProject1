"""Semantic Operation block support backed by YAML operation templates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.services.block_props import (
    OPERATION_PROPERTIES,
    extract_namespace,
    normalize_operation_block_props,
)
from app.services.operation_templates import (
    build_operation_props,
    flatten_operation_target,
    sanitize_operation_props as sanitize_template_operation_props,
    serialize_operation_props,
)


OPERATION_BLOCK_TYPE_ID = "operation"
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
    return {OPERATION_PROPERTIES: sanitize_template_operation_props(raw_props)}


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
        **serialize_operation_props(operation_props),
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
    return flatten_operation_target(extract_namespace(normalized, OPERATION_PROPERTIES))

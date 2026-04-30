"""Helpers for explicit document block property namespaces."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


DOCUMENT_PROPERTIES = "document_properties"
HEATING_PROPERTIES = "heating_properties"
DEFORMATION_PROPERTIES = "deformation_properties"
FURNACE_PROPERTIES = "furnace_properties"
OPERATION_PROPERTIES = "operation_properties"

PROPERTY_NAMESPACES = (
    DOCUMENT_PROPERTIES,
    HEATING_PROPERTIES,
    DEFORMATION_PROPERTIES,
    FURNACE_PROPERTIES,
    OPERATION_PROPERTIES,
)

TRANSIENT_BLOCK_PROP_KEYS = frozenset(
    {
        "title",
        "operation_type",
        "operation_template",
        "operation_templates",
        "operation_type_selector",
        "operation_block_parsing_rules",
        "parameters_calculation_mode_selector",
        "available_geometry_types",
        "selected_geometry",
        "billet_geometry_title",
        "editable_fields",
        "field_limits",
        "version",
        "created_at",
        "updated_at",
        "project_id",
        "source_document_id",
        "editor_user_id",
        "material_version_id",
    }
)

DOCUMENT_LEGACY_KEYS = frozenset(
    {
        "name",
        "heat_no",
        "finished_size",
        "remarks",
        "preview_status",
        "material_id",
        "geometry_type_id",
        "weight",
        "attributes",
        "mesh_elements",
        "section_numbering_start",
    }
)

HEATING_LEGACY_KEYS = frozenset({"furnace_class_id", "temperature"})
FURNACE_LEGACY_KEYS = frozenset({"furnace_class_id", "temperature"})
OPERATION_LEGACY_KEYS = frozenset(
    {
        "operation_template_id",
        "operation_template_version",
        "operation_kind",
        "operation_text",
        "rounding_table",
        "target",
        "template_snapshot",
    }
)


def as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def deep_merge(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(dict(left or {}))
    for key, value in dict(right or {}).items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(current, value)
        else:
            result[key] = deepcopy(value)
    return result


def empty_namespaced_props() -> dict[str, dict[str, Any]]:
    return {namespace: {} for namespace in PROPERTY_NAMESPACES}


def extract_namespace(props: Mapping[str, Any] | None, namespace: str) -> dict[str, Any]:
    return as_dict(as_dict(props).get(namespace))


def strip_transient_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in dict(props or {}).items()
        if key not in TRANSIENT_BLOCK_PROP_KEYS
    }


def normalize_document_block_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = strip_transient_props(props)
    document_properties = extract_namespace(raw, DOCUMENT_PROPERTIES)
    for key in DOCUMENT_LEGACY_KEYS:
        if key in raw:
            document_properties[key] = deepcopy(raw[key])
    return {DOCUMENT_PROPERTIES: document_properties}


def normalize_heating_block_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = strip_transient_props(props)
    heating_properties = extract_namespace(raw, HEATING_PROPERTIES)
    for key in HEATING_LEGACY_KEYS:
        if key in raw:
            heating_properties[key] = deepcopy(raw[key])
    return {HEATING_PROPERTIES: heating_properties}


def normalize_deformation_block_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = strip_transient_props(props)
    return {DEFORMATION_PROPERTIES: extract_namespace(raw, DEFORMATION_PROPERTIES)}


def normalize_furnace_block_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = strip_transient_props(props)
    furnace_properties = extract_namespace(raw, FURNACE_PROPERTIES)
    for key in FURNACE_LEGACY_KEYS:
        if key in raw:
            furnace_properties[key] = deepcopy(raw[key])
    return {FURNACE_PROPERTIES: furnace_properties}


def normalize_operation_block_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = strip_transient_props(props)
    operation_properties = extract_namespace(raw, OPERATION_PROPERTIES)
    for key in OPERATION_LEGACY_KEYS:
        # Frontend read models include top-level mirrors for operation fields.
        # Text/table editors write through the namespace; their stale top-level
        # mirrors must not overwrite edited namespaced values on save.
        if key in raw and not (key in {"operation_text", "rounding_table"} and key in operation_properties):
            operation_properties[key] = deepcopy(raw[key])
    return {OPERATION_PROPERTIES: operation_properties}


def flatten_effective_properties(*namespaces: Mapping[str, Any] | None) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for namespace in namespaces:
        flattened = deep_merge(flattened, namespace)
    return flattened

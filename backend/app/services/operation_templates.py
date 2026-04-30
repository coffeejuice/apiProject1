"""YAML-backed operation templates for semantic document Operation blocks."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml


TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "domain" / "operation_block_design_and_parsing_rules.yaml"
DEFAULT_OPERATION_TEMPLATE_ID = "operation.empty"


def _as_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, Mapping)]


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def _template_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    template_id = str(raw.get("id") or "").strip()
    if not template_id:
        raise ValueError("Operation template is missing id")

    label = str(raw.get("label") or template_id)
    return {
        "id": template_id,
        "version": int(raw.get("version") or 1),
        "label": label,
        "display_name": str(raw.get("display_name") or label),
        "category": str(raw.get("category") or "generic"),
        "operation_kind": str(raw.get("operation_kind") or "generic"),
        "compiler_handler": str(raw.get("compiler_handler") or "semantic_operation"),
        "insertable": bool(raw.get("insertable", True)),
        "materialize": bool(raw.get("materialize", True)),
        "input_method": str(raw.get("input_method") or "text"),
        "input_schema": _as_list(raw.get("input_schema")),
        "target_schema": _as_list(raw.get("target_schema")),
    }


@lru_cache(maxsize=1)
def _load_operation_document() -> dict[str, Any]:
    with TEMPLATES_PATH.open("r", encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream) or {}
    if not isinstance(loaded, Mapping):
        raise ValueError(f"{TEMPLATES_PATH} must contain a mapping")
    return dict(loaded)


@lru_cache(maxsize=1)
def load_operation_templates() -> tuple[dict[str, Any], ...]:
    loaded = _load_operation_document()
    raw_templates = loaded.get("templates") if isinstance(loaded, Mapping) else None
    if not isinstance(raw_templates, list):
        raise ValueError(f"{TEMPLATES_PATH} must contain a templates list")

    templates = tuple(_template_payload(raw) for raw in raw_templates if isinstance(raw, Mapping))
    template_ids = [template["id"] for template in templates]
    duplicate_ids = {template_id for template_id in template_ids if template_ids.count(template_id) > 1}
    if duplicate_ids:
        raise ValueError(f"Duplicate operation template ids: {', '.join(sorted(duplicate_ids))}")
    if DEFAULT_OPERATION_TEMPLATE_ID not in template_ids:
        raise ValueError(f"Missing default operation template {DEFAULT_OPERATION_TEMPLATE_ID}")
    return templates


def get_operation_type_selector() -> dict[str, Any]:
    return _as_dict(_load_operation_document().get("operation_type_selector"))


def get_parameters_calculation_mode_selector() -> dict[str, Any]:
    return _as_dict(_load_operation_document().get("parameters_calculation_mode_selector"))


def get_operation_block_parsing_rules() -> dict[str, Any]:
    return _as_dict(_load_operation_document().get("operation_block_parsing_rules"))


def get_operation_block_parsing_rule(template_id: str | None) -> dict[str, Any] | None:
    if not template_id:
        return None
    rules = get_operation_block_parsing_rules()
    rule = rules.get(template_id)
    return dict(rule) if isinstance(rule, Mapping) else None


def list_operation_templates(*, insertable_only: bool = False) -> list[dict[str, Any]]:
    templates = [dict(template) for template in load_operation_templates()]
    if insertable_only:
        return [template for template in templates if template.get("insertable", True)]
    return templates


def get_operation_template(template_id: str | None) -> dict[str, Any]:
    resolved_id = template_id or DEFAULT_OPERATION_TEMPLATE_ID
    for template in load_operation_templates():
        if template["id"] == resolved_id:
            return dict(template)
    raise KeyError(f"Unknown operation template: {resolved_id}")


def _build_target_defaults(template: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    calculation_selector = get_parameters_calculation_mode_selector()
    calculation_path = str(calculation_selector.get("target_path") or "")
    if calculation_path.startswith("target."):
        _set_nested(
            result,
            calculation_path.removeprefix("target."),
            calculation_selector.get("default", "manual"),
        )
    for field in _as_list(template.get("target_schema")):
        path = str(field.get("path") or "")
        if not path.startswith("target."):
            continue
        _set_nested(result, path.removeprefix("target."), field.get("default", ""))
    return result


def _merge_target_values(
    target: dict[str, Any],
    overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
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


def sanitize_operation_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw_props = dict(props or {})
    return build_operation_props(
        str(raw_props.get("operation_template_id") or DEFAULT_OPERATION_TEMPLATE_ID),
        raw_props,
    )


def serialize_operation_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    sanitized = sanitize_operation_props(props)
    template = get_operation_template(str(sanitized.get("operation_template_id") or DEFAULT_OPERATION_TEMPLATE_ID))
    return {
        **sanitized,
        "title": template.get("display_name") or template["label"],
        "operation_template": template,
        "operation_templates": list_operation_templates(),
        "operation_type_selector": get_operation_type_selector(),
        "operation_block_parsing_rules": get_operation_block_parsing_rules(),
        "parameters_calculation_mode_selector": get_parameters_calculation_mode_selector(),
    }


def flatten_operation_target(props: Mapping[str, Any] | None) -> dict[str, Any]:
    raw_props = dict(props or {})
    target = raw_props.get("target")
    if not isinstance(target, Mapping):
        return {}

    template_id = raw_props.get("operation_template_id")
    template: Mapping[str, Any] = raw_props.get("template_snapshot") if isinstance(raw_props.get("template_snapshot"), Mapping) else {}
    if not template and template_id:
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

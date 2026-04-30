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
from app.models.document.document_operation import DocumentOperation
from app.services.block_props import (
    DEFORMATION_PROPERTIES,
    DOCUMENT_PROPERTIES,
    FURNACE_PROPERTIES,
    HEATING_PROPERTIES,
    OPERATION_PROPERTIES,
    as_dict,
    deep_merge,
    extract_namespace,
    flatten_effective_properties,
    normalize_deformation_block_props,
    normalize_document_block_props,
    normalize_furnace_block_props,
    normalize_heating_block_props,
    normalize_operation_block_props,
)
from app.services.operation_templates import (
    build_operation_props,
    get_operation_block_parsing_rule,
)


DOCUMENT_BLOCK_TYPE_ID = "document"
HEATING_BLOCK_TYPE_ID = "heating"
DEFORMATION_BLOCK_TYPE_ID = "deformation"
FURNACE_BLOCK_TYPE_ID = "furnace"
OPERATION_BLOCK_TYPE_ID = "operation"
EMPTY_OPERATION_TEMPLATE_ID = "operation.empty"
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
    return build_operation_props(template_id, {"target": dict(target)})


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
            "radial_feed": _nested_value(deformation_properties, "deformation_variables.radial_feed"),
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


def _operation_effective_properties(
    *,
    document_properties: Mapping[str, Any],
    heating_properties: Mapping[str, Any],
    deformation_properties: Mapping[str, Any],
    furnace_properties: Mapping[str, Any] | None = None,
    operation_properties: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    operation_values = dict(operation_properties or {})
    target = operation_values.pop("target", None)
    if isinstance(target, Mapping):
        operation_values = deep_merge(operation_values, target)
    return flatten_effective_properties(
        document_properties,
        heating_properties,
        deformation_properties,
        furnace_properties or {},
        operation_values,
    )


def _delete_existing(session: Session, document_id: int) -> None:
    existing = session.scalars(
        select(DocumentOperation).where(DocumentOperation.document_id == document_id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()


def _add_operation_row(
    session: Session,
    *,
    document_id: int,
    source_block_id: Any,
    operation_order: int,
    operation_order_in_block: int,
    source_block_type_id: str,
    operation_properties: Mapping[str, Any],
    document_properties: Mapping[str, Any],
    heating_properties: Mapping[str, Any],
    deformation_properties: Mapping[str, Any],
    furnace_properties: Mapping[str, Any] | None = None,
    source_text_hash: str | None = None,
    parse_status: str = "valid",
    parse_errors: list[dict[str, Any]] | None = None,
    parse_warnings: list[dict[str, Any]] | None = None,
) -> None:
    template_id = operation_properties.get("operation_template_id")
    operation_kind = _operation_kind_from_template(str(template_id) if template_id else None, operation_properties)
    template_snapshot = as_dict(operation_properties.get("template_snapshot"))
    effective_properties = _operation_effective_properties(
        document_properties=document_properties,
        heating_properties=heating_properties,
        deformation_properties=deformation_properties,
        furnace_properties=furnace_properties,
        operation_properties=operation_properties,
    )

    session.add(
        DocumentOperation(
            document_id=document_id,
            source_block_id=source_block_id,
            operation_order=operation_order,
            operation_order_in_block=operation_order_in_block,
            source_block_type_id=source_block_type_id,
            operation_template_id=str(template_id) if template_id else None,
            operation_kind=operation_kind,
            label_snapshot=_operation_label(operation_properties),
            document_properties=deepcopy(dict(document_properties)),
            heating_properties=deepcopy(dict(heating_properties)),
            deformation_properties=deepcopy(dict(deformation_properties)),
            furnace_properties=deepcopy(dict(furnace_properties or {})),
            operation_properties=deepcopy(dict(operation_properties)),
            effective_properties=effective_properties,
            template_snapshot=template_snapshot,
            source_text_hash=source_text_hash,
            parse_status=parse_status,
            parse_errors=parse_errors or [],
            parse_warnings=parse_warnings or [],
        )
    )


def regenerate_document_operations(session: Session, document_id: int) -> int:
    """Rebuild materialized operation rows from explicit block props.

    Inheritance is evaluated only here. `document_blocks.props` remains an
    explicit user-authored source and is not overwritten with inherited values.
    """

    _delete_existing(session, document_id)

    document_properties: dict[str, Any] = {}
    heating_properties: dict[str, Any] = {}
    deformation_properties: dict[str, Any] = {}
    operation_order = 1

    for block in _ordered_blocks(session, document_id):
        normalized_props = normalize_props_for_block_type(block.block_type_id, block.props)

        if block.block_type_id == DOCUMENT_BLOCK_TYPE_ID:
            document_properties = deep_merge(
                document_properties,
                extract_namespace(normalized_props, DOCUMENT_PROPERTIES),
            )
            continue

        if block.block_type_id == HEATING_BLOCK_TYPE_ID:
            heating_properties = deep_merge(
                heating_properties,
                extract_namespace(normalized_props, HEATING_PROPERTIES),
            )
            continue

        if block.block_type_id == DEFORMATION_BLOCK_TYPE_ID:
            deformation_properties = deep_merge(
                deformation_properties,
                extract_namespace(normalized_props, DEFORMATION_PROPERTIES),
            )
            continue

        if block.block_type_id == FURNACE_BLOCK_TYPE_ID:
            furnace_properties = extract_namespace(normalized_props, FURNACE_PROPERTIES)
            _add_operation_row(
                session,
                document_id=document_id,
                source_block_id=block.block_id,
                operation_order=operation_order,
                operation_order_in_block=0,
                source_block_type_id=FURNACE_BLOCK_TYPE_ID,
                operation_properties={
                    "operation_template_id": "furnace",
                    "operation_kind": "furnace",
                    "template_snapshot": {"id": "furnace", "display_name": "Furnace", "label": "Furnace"},
                },
                document_properties=document_properties,
                heating_properties=heating_properties,
                deformation_properties=deformation_properties,
                furnace_properties=furnace_properties,
            )
            operation_order += 1
            continue

        if block.block_type_id == OPERATION_BLOCK_TYPE_ID:
            operation_properties = extract_namespace(normalized_props, OPERATION_PROPERTIES)
            selected_template_id = str(operation_properties.get("operation_template_id") or "")
            selected_parsing_rule = get_operation_block_parsing_rule(selected_template_id)
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
                            document_id=document_id,
                            source_block_id=block.block_id,
                            operation_order=operation_order,
                            operation_order_in_block=row_index,
                            source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                            operation_properties=parsed_operation_properties,
                            document_properties=document_properties,
                            heating_properties=heating_properties,
                            deformation_properties=deformation_properties,
                            source_text_hash=source_text_hash,
                        )
                    except Exception as exc:
                        _add_operation_row(
                            session,
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
                            document_properties=document_properties,
                            heating_properties=heating_properties,
                            deformation_properties=deformation_properties,
                            source_text_hash=source_text_hash,
                            parse_status="error",
                            parse_errors=[{"row": row_index, "message": str(exc)}],
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
                        document_properties=document_properties,
                        heating_properties=heating_properties,
                        deformation_properties=deformation_properties,
                        source_text_hash=source_text_hash,
                        parse_status="error",
                        parse_errors=[{"sentence": sentence_index, "message": "Initial state is allowed only in first position"}],
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
                        deformation_properties=deformation_properties,
                    )
                    parsed_operation_properties["operation_text"] = operation_text
                    parsed_operation_properties["source_sentence"] = sentence
                    _add_operation_row(
                        session,
                        document_id=document_id,
                        source_block_id=block.block_id,
                        operation_order=operation_order,
                        operation_order_in_block=sentence_index,
                        source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                        operation_properties=parsed_operation_properties,
                        document_properties=document_properties,
                        heating_properties=heating_properties,
                        deformation_properties=deformation_properties,
                        source_text_hash=source_text_hash,
                        parse_warnings=parse_warnings,
                    )
                except Exception as exc:
                    _add_operation_row(
                        session,
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
                        document_properties=document_properties,
                        heating_properties=heating_properties,
                        deformation_properties=deformation_properties,
                        source_text_hash=source_text_hash,
                        parse_status="error",
                        parse_errors=[{"sentence": sentence_index, "message": str(exc)}],
                    )
                operation_order += 1
            if parsed_text_sentences > 0:
                continue

            template_id = operation_properties.get("operation_template_id")
            if not template_id or str(template_id) == EMPTY_OPERATION_TEMPLATE_ID:
                continue
            if selected_parsing_rule is not None:
                continue

            _add_operation_row(
                session,
                document_id=document_id,
                source_block_id=block.block_id,
                operation_order=operation_order,
                operation_order_in_block=0,
                source_block_type_id=OPERATION_BLOCK_TYPE_ID,
                operation_properties=operation_properties,
                document_properties=document_properties,
                heating_properties=heating_properties,
                deformation_properties=deformation_properties,
            )
            operation_order += 1

    session.flush()
    return operation_order - 1

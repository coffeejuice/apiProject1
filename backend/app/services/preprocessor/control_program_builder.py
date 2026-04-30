"""Control-program construction helpers derived from editable process cards."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library.library import TimeBetweenOperations
from app.services.operation_templates import load_operation_templates
from app.services.preprocessor.operation_keys import (
    CUTTING_COLD_SAW_KEEP_PERCENT,
    FURNACE_TEMPLATE_ID,
    GEOMETRY_TEMPLATE_PREFIX,
    HEATING_TEMPERATURE_DURATION_TEMPLATE_ID,
    NON_SIMULATION_OPERATION_TEMPLATE_IDS,
    OPERATION_EMPTY_TEMPLATE_ID,
    UPSETTING_TEMPLATE_IDS,
)
from app.services.preprocessor.geometry import GEOMETRY_TYPES


LOGGER = logging.getLogger(__name__)


class ControlProgramError(ValueError):
    """Raised when control-program metadata is inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class OperationTypeDefinition:
    """Semantic preprocessing metadata for one compiler-compatible operation."""

    operation_template_id: str
    type_id: int | None
    parent_type_id: str | None
    row: int
    text_id: str
    library_name: str
    process_name: str
    labels: tuple[str, ...]
    db_column_names: tuple[str, ...]
    is_simulation: bool
    is_geometry: bool
    is_press: bool
    is_feed: bool
    trigger: str | None
    is_initialize: bool
    is_accumulate: bool
    is_keep: bool
    deformation_type: str | None
    speed_column_name: str | None


@dataclass(frozen=True, slots=True)
class TimeBetweenOperationDefinition:
    """Normalized subset of `time_between_operations` used by preprocessing."""

    first_operation_template_id: str
    second_operation_template_id: str
    press_id: int
    time_mean_seconds: float
    time_sigma_seconds: float | None

    @classmethod
    def from_model(cls, model: TimeBetweenOperations) -> "TimeBetweenOperationDefinition":
        return cls(
            first_operation_template_id=model.first_operation_template_id,
            second_operation_template_id=model.second_operation_template_id,
            press_id=model.press_id,
            time_mean_seconds=float(model.time_mean or 0.0),
            time_sigma_seconds=float(model.time_sigma) if model.time_sigma is not None else None,
        )


@dataclass(frozen=True, slots=True)
class OperationLibrarySnapshot:
    """Runtime-prepared YAML metadata needed by the preprocessor."""

    operations_by_template: dict[str, OperationTypeDefinition]
    operations_by_type: dict[int, OperationTypeDefinition]
    ordered_children_by_parent: dict[str | None, tuple[str, ...]]
    type_tree: dict[str, dict[str, Any]]
    time_between_operations: dict[tuple[str, str, int], TimeBetweenOperationDefinition]

    @property
    def root_type_ids(self) -> tuple[str, ...]:
        """Return the ordered top-level operation template ids."""

        return self.ordered_children_by_parent.get(None, ())

    def get_operation(
        self,
        operation_template_id: str | None = None,
        *,
        type_id: int | None = None,
    ) -> OperationTypeDefinition:
        """Return one operation definition by semantic template id, with geometry fallback."""

        if operation_template_id:
            try:
                return self.operations_by_template[operation_template_id]
            except KeyError as exc:
                raise ControlProgramError(
                    f"Unknown preprocessor operation_template_id={operation_template_id}"
                ) from exc
        if type_id is not None:
            try:
                return self.operations_by_type[type_id]
            except KeyError as exc:
                raise ControlProgramError(f"Unknown preprocessor geometry type_id={type_id}") from exc
        raise ControlProgramError("Operation lookup requires operation_template_id or geometry type_id")

    def get_time_between_operations(
        self,
        *,
        first_operation_template_id: str,
        second_operation_template_id: str,
        press_id: int,
    ) -> float:
        """Return the configured mean time between two operations for one press mode."""

        key = (first_operation_template_id, second_operation_template_id, press_id)
        record = self.time_between_operations.get(key)
        if record is None:
            raise ControlProgramError(
                "No time_between_operations record for "
                f"first_operation_template_id={first_operation_template_id}, "
                f"second_operation_template_id={second_operation_template_id}, press_id={press_id}"
            )
        return record.time_mean_seconds


def _target_schema_field_names(template: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    for field in template.get("target_schema") or ():
        if not isinstance(field, Mapping):
            continue
        path = str(field.get("path") or "")
        if not path.startswith("target."):
            continue
        name = path.removeprefix("target.")
        if name and "." not in name:
            names.append(name)
    return tuple(names)


def _target_schema_labels(template: Mapping[str, Any]) -> tuple[str, ...]:
    labels: list[str] = []
    for field in template.get("target_schema") or ():
        if not isinstance(field, Mapping):
            continue
        label = str(field.get("label") or "").strip()
        if label:
            labels.append(label)
    return tuple(labels)


def _template_deformation_type(template: Mapping[str, Any]) -> str | None:
    template_id = str(template.get("id") or "")
    category = str(template.get("category") or "")
    operation_kind = str(template.get("operation_kind") or "")

    if template_id in UPSETTING_TEMPLATE_IDS or operation_kind == "upsetting":
        return "upsetting"
    if category in {"prolongation", "rounding"} or operation_kind == "prolongation":
        return "axial_prolongation"
    if category == "radial" or operation_kind == "radial":
        return "radial_prolongation"
    if category == "transversal" or operation_kind == "transversal":
        return "full_die"
    if category == "cutting":
        return "cold_sawing" if template_id == CUTTING_COLD_SAW_KEEP_PERCENT else "hot_cutting"
    return None


def _template_speed_column_name(template: Mapping[str, Any], deformation_type: str | None) -> str | None:
    category = str(template.get("category") or "")
    if deformation_type == "upsetting":
        return "speed_upsetting"
    if deformation_type == "full_die":
        return "speed_transversal_cogging"
    if category in {"prolongation", "rounding", "radial", "cutting"}:
        return "speed_prolongation"
    return None


def _definition_from_operation_template(template: Mapping[str, Any], *, row: int) -> OperationTypeDefinition | None:
    template_id = str(template.get("id") or "").strip()
    if (
        not template_id
        or template_id == OPERATION_EMPTY_TEMPLATE_ID
        or not bool(template.get("materialize", True))
    ):
        return None

    deformation_type = _template_deformation_type(template)
    is_simulation = template_id not in NON_SIMULATION_OPERATION_TEMPLATE_IDS
    return OperationTypeDefinition(
        operation_template_id=template_id,
        type_id=None,
        parent_type_id=None,
        row=row,
        text_id=template_id,
        library_name=str(template.get("label") or template_id),
        process_name=str(template.get("display_name") or template.get("label") or template_id),
        labels=_target_schema_labels(template),
        db_column_names=_target_schema_field_names(template),
        is_simulation=is_simulation,
        is_geometry=False,
        is_press=False,
        is_feed=False,
        trigger="keep",
        is_initialize=False,
        is_accumulate=False,
        is_keep=True,
        deformation_type=deformation_type,
        speed_column_name=_template_speed_column_name(template, deformation_type),
    )


def _geometry_operation_definitions() -> list[OperationTypeDefinition]:
    definitions: list[OperationTypeDefinition] = []
    for row, geometry in enumerate(sorted(GEOMETRY_TYPES.values(), key=lambda item: item.type_id), start=1):
        label = f"Billet geometry: {geometry.shape}"
        definitions.append(
            OperationTypeDefinition(
                type_id=geometry.type_id,
                operation_template_id=f"{GEOMETRY_TEMPLATE_PREFIX}{geometry.type_id}",
                parent_type_id=None,
                row=row,
                text_id=f"{GEOMETRY_TEMPLATE_PREFIX}{geometry.type_id}",
                library_name=label,
                process_name=label,
                labels=geometry.labels,
                db_column_names=geometry.labels,
                is_simulation=True,
                is_geometry=True,
                is_press=False,
                is_feed=False,
                trigger="accumulate",
                is_initialize=False,
                is_accumulate=True,
                is_keep=False,
                deformation_type=None,
                speed_column_name=None,
            )
        )
    return definitions


def _builtin_operation_definitions() -> list[OperationTypeDefinition]:
    return [
        OperationTypeDefinition(
            operation_template_id=FURNACE_TEMPLATE_ID,
            type_id=None,
            parent_type_id=None,
            row=1,
            text_id=FURNACE_TEMPLATE_ID,
            library_name="Furnace",
            process_name="Furnace",
            labels=("Furnace class", "Temperature"),
            db_column_names=("furnace_class_id", "temperature"),
            is_simulation=False,
            is_geometry=False,
            is_press=False,
            is_feed=False,
            trigger="accumulate",
            is_initialize=False,
            is_accumulate=True,
            is_keep=False,
            deformation_type=None,
            speed_column_name=None,
        ),
        OperationTypeDefinition(
            operation_template_id=HEATING_TEMPERATURE_DURATION_TEMPLATE_ID,
            type_id=None,
            parent_type_id=None,
            row=2,
            text_id=HEATING_TEMPERATURE_DURATION_TEMPLATE_ID,
            library_name="Heating",
            process_name="Heating",
            labels=("Temperature", "Duration"),
            db_column_names=("temperature", "duration"),
            is_simulation=True,
            is_geometry=False,
            is_press=False,
            is_feed=False,
            trigger="keep",
            is_initialize=False,
            is_accumulate=False,
            is_keep=True,
            deformation_type=None,
            speed_column_name=None,
        ),
    ]


def build_yaml_operation_definitions() -> list[OperationTypeDefinition]:
    """Build compiler metadata from current YAML plus semantic built-ins."""

    definitions = _geometry_operation_definitions() + _builtin_operation_definitions()
    for row, template in enumerate(load_operation_templates(), start=1):
        definition = _definition_from_operation_template(template, row=row)
        if definition is not None:
            definitions.append(definition)
    return definitions


def build_ordered_children_by_parent(
    operations: Iterable[OperationTypeDefinition],
) -> dict[str | None, tuple[str, ...]]:
    """Build a parent -> ordered child-template-id mapping from operation metadata."""

    buckets: dict[str | None, list[OperationTypeDefinition]] = defaultdict(list)
    for operation in operations:
        buckets[operation.parent_type_id].append(operation)

    return {
        parent_type_id: tuple(
            operation.operation_template_id
            for operation in sorted(children, key=lambda item: (item.row, item.operation_template_id))
        )
        for parent_type_id, children in buckets.items()
    }


def build_operations_tree(
    ordered_children_by_parent: Mapping[str | None, Sequence[str]],
) -> dict[str, dict[str, Any]]:
    """Build the nested operation-template tree from ordered parent/child links."""

    def recurse(parent_type_id: str | None) -> dict[str, dict[str, Any]]:
        return {
            child_template_id: recurse(child_template_id)
            for child_template_id in ordered_children_by_parent.get(parent_type_id, ())
        }

    return recurse(None)


def flatten_operations_tree(type_tree: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    """Flatten an operation-template tree in pre-order."""

    ordered: list[str] = []

    def recurse(branch: Mapping[str, Mapping[str, Any]]) -> None:
        for template_id, subtree in branch.items():
            ordered.append(template_id)
            recurse(subtree)

    recurse(type_tree)
    return tuple(ordered)


def load_operation_library_snapshot(session: Session) -> OperationLibrarySnapshot:
    """Load preprocessing metadata from YAML and timing data from the database."""

    time_models = list(session.scalars(select(TimeBetweenOperations)).all())

    operations = build_yaml_operation_definitions()
    operations_by_template = {operation.operation_template_id: operation for operation in operations}
    operations_by_type = {
        operation.type_id: operation
        for operation in operations
        if operation.type_id is not None
    }
    ordered_children = build_ordered_children_by_parent(operations)
    type_tree = build_operations_tree(ordered_children)
    time_between_operations = {
        (record.first_operation_template_id, record.second_operation_template_id, record.press_id): record
        for record in (TimeBetweenOperationDefinition.from_model(model) for model in time_models)
    }

    LOGGER.info(
        "Loaded YAML preprocessing snapshot operations=%s time_between_records=%s",
        len(operations_by_template),
        len(time_between_operations),
    )

    return OperationLibrarySnapshot(
        operations_by_template=operations_by_template,
        operations_by_type=operations_by_type,
        ordered_children_by_parent=ordered_children,
        type_tree=type_tree,
        time_between_operations=time_between_operations,
    )

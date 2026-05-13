"""Control-program construction helpers derived from document operation outputs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library.library import TimeBetweenOperations
from app.services.preprocessor.operation_keys import (
    CUTTING_COLD_SAW_KEEP_PERCENT,
    CUTTING_HOT_KEEP_PERCENT,
    DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
    FURNACE_TEMPLATE_ID,
    GEOMETRY_TEMPLATE_PREFIX,
    HEATING_TEMPERATURE_DURATION_TEMPLATE_ID,
    TRANSVERSE_ALL_IN_ONE,
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
    operation_display_name: str
    labels: tuple[str, ...]
    db_column_names: tuple[str, ...]
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
    """Runtime-prepared semantic metadata needed by the preprocessor."""

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


@dataclass(frozen=True, slots=True)
class SemanticOperationDefinitionSpec:
    """Preprocessor-local semantic operation metadata."""

    operation_template_id: str
    label: str
    operation_display_name: str
    labels: tuple[str, ...]
    db_column_names: tuple[str, ...]
    deformation_type: str | None
    speed_column_name: str | None


SEMANTIC_OPERATION_DEFINITION_SPECS: tuple[SemanticOperationDefinitionSpec, ...] = (
    SemanticOperationDefinitionSpec(
        "upsetting.rotation_height",
        "Upsetting: rotation and height",
        "Upsetting: rotation and height",
        ("Rotate before upsetting", "Height of upsetting"),
        ("rotation", "height"),
        "upsetting",
        "speed_upsetting",
    ),
    SemanticOperationDefinitionSpec(
        "upsetting.tail_flattening",
        "Upsetting: tail flattening",
        "Upsetting: tail flattening",
        ("Rotate before tail flattening", "Stroke distance of tail flattening"),
        ("rotation", "stroke"),
        "upsetting",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "upsetting.single_stroke",
        "Upsetting: single stroke",
        "Upsetting: single stroke",
        ("Rotate before upsetting", "Height of upsetting"),
        ("rotation", "height"),
        "upsetting",
        "speed_upsetting",
    ),
    SemanticOperationDefinitionSpec(
        "upsetting.three_strokes",
        "Upsetting: three strokes",
        "Upsetting: three strokes",
        ("Rotate before upsetting", "Height of upsetting"),
        ("rotation", "height"),
        "upsetting",
        "speed_upsetting",
    ),
    SemanticOperationDefinitionSpec(
        "upsetting.tail_chamfering",
        "Upsetting: tail chamfering",
        "Upsetting: tail chamfering",
        ("Rotate before tail chamfering", "Stroke distance of tail chamfering"),
        ("rotation", "stroke"),
        "upsetting",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "prolongation.rotation_height",
        "Prolongation: rotation and height",
        "Prolongation: rotation and height",
        ("Rotation before prolongation", "Height of prolongation"),
        ("rotation", "height"),
        "axial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "prolongation.height_bites",
        "Prolongation: height and bites",
        "Prolongation: height and bites",
        ("Rotation before prolongation", "Height of prolongation", "Number of bites"),
        ("rotation", "height", "num_of_bites"),
        "axial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "prolongation.skip_bites",
        "Prolongation: skip bites",
        "Prolongation: skip bites",
        ("Rotation before prolongation", "Height of prolongation", "Number of bites", "Skip bites"),
        ("rotation", "height", "num_of_bites", "skip_bites"),
        "axial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "rounding.spiral_one_rotation",
        "Spiral rounding: one rotation per feed",
        "Spiral rounding: one rotation per feed",
        ("Final diameter", "Feed", "Angle", "Rotations per Feed", "Speed", "Compiler diameter", "Compiler rotation per bite"),
        ("final_diameter", "feed", "angle", "rotations_per_feed", "speed", "diameter", "rotation_per_bite"),
        "axial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "rounding.spiral_three_rotations",
        "Spiral rounding: three rotations per feed",
        "Spiral rounding: three rotations per feed",
        ("Final diameter", "Feed", "Angle", "Rotations per Feed", "Speed", "Compiler diameter", "Compiler rotation per bite"),
        ("final_diameter", "feed", "angle", "rotations_per_feed", "speed", "diameter", "rotation_per_bite"),
        "axial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "radial.rotation_height_feed",
        "Radial: rotation, height and feed",
        "Radial: rotation, height and feed",
        ("Rotation around manipulator axis", "Height", "Feed"),
        ("rotation_manipulator", "height", "radial_feed"),
        "radial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "radial.height_bites",
        "Radial: height and number of bites",
        "Radial: height and number of bites",
        ("Rotation around manipulator axis", "Height", "Number of bites"),
        ("rotation_manipulator", "height", "num_of_bites"),
        "radial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "radial.press_axis_feed",
        "Radial: press-axis feed",
        "Radial: press-axis feed",
        ("Rotate around press axis", "Height of upsetting", "Radial feed"),
        ("rotation", "height", "radial_feed"),
        "radial_prolongation",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "radial.initial_rotations",
        "Radial: initial rotations",
        "Radial: initial rotations",
        ("1st X rotation", "2nd Y rotation", "3rd X rotation", "4th Y rotation"),
        ("rotation_1_x", "rotation_2_y", "rotation_3_x", "rotation_4_y"),
        "radial_prolongation",
        None,
    ),
    SemanticOperationDefinitionSpec(
        TRANSVERSE_ALL_IN_ONE,
        "Transverse cogging: all in one",
        "Transverse cogging: all in one",
        ("Rotation before bite", "Height of bite", "Number of bites", "Skip bites"),
        ("rotation", "height", "num_of_bites", "skip_bites"),
        "full_die",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        "transversal.rotation_height",
        "Transversal cogging: rotation and height",
        "Transversal cogging: rotation and height",
        ("Rotation before bite", "Height of bite"),
        ("rotation", "height"),
        "full_die",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        CUTTING_HOT_KEEP_PERCENT,
        "Hot cutting: keep percent",
        "Hot cutting: keep percent",
        ("Pieces count", "Keep piece number", "Keep length ratio"),
        ("pieces_count", "piece_number", "percentage_to_keep"),
        "hot_cutting",
        "speed_prolongation",
    ),
    SemanticOperationDefinitionSpec(
        CUTTING_COLD_SAW_KEEP_PERCENT,
        "Cold saw: keep percent",
        "Cold saw: keep percent",
        ("Pieces count", "Keep piece number", "Keep length ratio"),
        ("pieces_count", "piece_number", "percentage_to_keep"),
        "cold_sawing",
        "speed_prolongation",
    ),
)


def _semantic_operation_definitions() -> list[OperationTypeDefinition]:
    definitions: list[OperationTypeDefinition] = []
    for row, spec in enumerate(SEMANTIC_OPERATION_DEFINITION_SPECS, start=1):
        definitions.append(
            OperationTypeDefinition(
                operation_template_id=spec.operation_template_id,
                type_id=None,
                parent_type_id=None,
                row=row,
                text_id=spec.operation_template_id,
                library_name=spec.label,
                operation_display_name=spec.operation_display_name,
                labels=spec.labels,
                db_column_names=spec.db_column_names,
                is_geometry=False,
                is_press=False,
                is_feed=False,
                trigger="keep",
                is_initialize=False,
                is_accumulate=False,
                is_keep=True,
                deformation_type=spec.deformation_type,
                speed_column_name=spec.speed_column_name,
            )
        )
    return definitions


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
                operation_display_name=label,
                labels=geometry.labels,
                db_column_names=geometry.labels,
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
            operation_template_id=DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
            type_id=None,
            parent_type_id=None,
            row=0,
            text_id=DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
            library_name="Billet",
            operation_display_name="Document initial data",
            labels=(
                "Document name",
                "Heat No",
                "Finished size",
                "Material",
                "Input stock geometry",
                "Input stock weight",
                "Mesh elements",
            ),
            db_column_names=(
                "document_info.name",
                "production_data.heat_no",
                "production_data.finished_size",
                "production_data.remarks",
                "material.material_id",
                "material.material_name",
                "input_stock.geometry_type_id",
                "input_stock.geometry_type_name",
                "input_stock.weight_kg",
                "input_stock.volume_mm3",
                "input_stock.attributes",
                "mesh.mesh_elements",
            ),
            is_geometry=True,
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
            operation_template_id=FURNACE_TEMPLATE_ID,
            type_id=None,
            parent_type_id=None,
            row=1,
            text_id=FURNACE_TEMPLATE_ID,
            library_name="Furnace",
            operation_display_name="Furnace",
            labels=("Furnace class", "Temperature"),
            db_column_names=("furnace_class_id", "temperature"),
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
            operation_display_name="Heating",
            labels=("Temperature", "Duration"),
            db_column_names=("temperature", "duration"),
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


def build_semantic_operation_definitions() -> list[OperationTypeDefinition]:
    """Build compiler metadata from preprocessor-local semantic definitions."""

    return (
        _geometry_operation_definitions()
        + _builtin_operation_definitions()
        + _semantic_operation_definitions()
    )


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
    """Load preprocessing metadata from local semantic definitions and timing data."""

    time_models = list(session.scalars(select(TimeBetweenOperations)).all())

    operations = build_semantic_operation_definitions()
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
        "Loaded semantic preprocessing snapshot operations=%s time_between_records=%s",
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

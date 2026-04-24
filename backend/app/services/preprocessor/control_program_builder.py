"""Control-program construction helpers derived from editable process cards."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library.library import OperationsLibrary, TimeBetweenOperations


LOGGER = logging.getLogger(__name__)


class ControlProgramError(ValueError):
    """Raised when control-program metadata is inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class OperationTypeDefinition:
    """Normalized subset of `document_blocks_library` used by preprocessing."""

    type_id: int
    parent_type_id: int | None
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

    @classmethod
    def from_model(cls, model: OperationsLibrary) -> "OperationTypeDefinition":
        return cls(
            type_id=model.type_id,
            parent_type_id=model.parent_type_id,
            row=model.row,
            text_id=model.text_id,
            library_name=model.library_name,
            process_name=model.process_name,
            labels=split_legacy_pipe_string(model.labels),
            db_column_names=split_legacy_pipe_string(model.db_column_names),
            is_simulation=model.is_simulation,
            is_geometry=model.is_geometry,
            is_press=model.is_press,
            is_feed=model.is_feed,
            trigger=model.trigger,
            is_initialize=model.is_initialize,
            is_accumulate=model.is_accumulate,
            is_keep=model.is_keep,
            deformation_type=model.deformation_type,
            speed_column_name=model.speed_column_name,
        )


@dataclass(frozen=True, slots=True)
class TimeBetweenOperationDefinition:
    """Normalized subset of `time_between_operations` used by preprocessing."""

    first_operation_type_id: int
    second_operation_type_id: int
    press_id: int
    time_mean_seconds: float
    time_sigma_seconds: float | None

    @classmethod
    def from_model(cls, model: TimeBetweenOperations) -> "TimeBetweenOperationDefinition":
        return cls(
            first_operation_type_id=model.first_operation_type_id,
            second_operation_type_id=model.second_operation_type_id,
            press_id=model.press_id,
            time_mean_seconds=float(model.time_mean or 0.0),
            time_sigma_seconds=float(model.time_sigma) if model.time_sigma is not None else None,
        )


@dataclass(frozen=True, slots=True)
class OperationLibrarySnapshot:
    """Runtime-prepared view of operation metadata needed by the preprocessor."""

    operations_by_type: dict[int, OperationTypeDefinition]
    ordered_children_by_parent: dict[int | None, tuple[int, ...]]
    type_tree: dict[int, dict[int, Any]]
    time_between_operations: dict[tuple[int, int, int], TimeBetweenOperationDefinition]

    @property
    def root_type_ids(self) -> tuple[int, ...]:
        """Return the ordered top-level operation type ids."""

        return self.ordered_children_by_parent.get(None, ())

    def get_operation(self, type_id: int) -> OperationTypeDefinition:
        """Return one operation type definition or fail with a clear error."""

        try:
            return self.operations_by_type[type_id]
        except KeyError as exc:
            raise ControlProgramError(f"Unknown document_blocks_library type_id={type_id}") from exc

    def get_time_between_operations(
        self,
        *,
        first_operation_type_id: int,
        second_operation_type_id: int,
        press_id: int,
    ) -> float:
        """Return the configured mean time between two operations for one press mode."""

        key = (first_operation_type_id, second_operation_type_id, press_id)
        record = self.time_between_operations.get(key)
        if record is None:
            raise ControlProgramError(
                "No time_between_operations record for "
                f"first_operation_type_id={first_operation_type_id}, "
                f"second_operation_type_id={second_operation_type_id}, press_id={press_id}"
            )
        return record.time_mean_seconds


def split_legacy_pipe_string(value: str | None) -> tuple[str, ...]:
    """Convert a legacy `a|b|c` string into a stable tuple."""

    if value is None:
        return ()
    parts = [part.strip() for part in value.split("|")]
    return tuple(part for part in parts if part)


def build_ordered_children_by_parent(
    operations: Iterable[OperationTypeDefinition],
) -> dict[int | None, tuple[int, ...]]:
    """Build a parent -> ordered child-type-id mapping from operations-library rows."""

    buckets: dict[int | None, list[OperationTypeDefinition]] = defaultdict(list)
    for operation in operations:
        buckets[operation.parent_type_id].append(operation)

    return {
        parent_type_id: tuple(
            operation.type_id
            for operation in sorted(children, key=lambda item: (item.row, item.type_id))
        )
        for parent_type_id, children in buckets.items()
    }


def build_operations_tree(
    ordered_children_by_parent: Mapping[int | None, Sequence[int]],
) -> dict[int, dict[int, Any]]:
    """Build the nested operation-type tree from ordered parent/child links."""

    def recurse(parent_type_id: int | None) -> dict[int, dict[int, Any]]:
        return {
            child_type_id: recurse(child_type_id)
            for child_type_id in ordered_children_by_parent.get(parent_type_id, ())
        }

    return recurse(None)


def flatten_operations_tree(type_tree: Mapping[int, Mapping[int, Any]]) -> tuple[int, ...]:
    """Flatten an operation-type tree in the same pre-order used by the old code."""

    ordered: list[int] = []

    def recurse(branch: Mapping[int, Mapping[int, Any]]) -> None:
        for type_id, subtree in branch.items():
            ordered.append(type_id)
            recurse(subtree)

    recurse(type_tree)
    return tuple(ordered)


def load_operation_library_snapshot(session: Session) -> OperationLibrarySnapshot:
    """Load the migrated preprocessing library subset from the current database."""

    operation_models = list(session.scalars(select(OperationsLibrary)).all())
    time_models = list(session.scalars(select(TimeBetweenOperations)).all())

    operations = [OperationTypeDefinition.from_model(model) for model in operation_models]
    operations_by_type = {operation.type_id: operation for operation in operations}
    ordered_children = build_ordered_children_by_parent(operations)
    type_tree = build_operations_tree(ordered_children)
    time_between_operations = {
        (record.first_operation_type_id, record.second_operation_type_id, record.press_id): record
        for record in (TimeBetweenOperationDefinition.from_model(model) for model in time_models)
    }

    LOGGER.info(
        "Loaded preprocessing library snapshot operations=%s time_between_records=%s",
        len(operations_by_type),
        len(time_between_operations),
    )

    return OperationLibrarySnapshot(
        operations_by_type=operations_by_type,
        ordered_children_by_parent=ordered_children,
        type_tree=type_tree,
        time_between_operations=time_between_operations,
    )

"""High-level preprocessing compiler entrypoints."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
import math
from collections.abc import Callable
from typing import Any, Iterator, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library.die import Die, DieAssembly
from app.models.library.material import Material
from app.models.library.press import PressMode
from app.services.preprocessor.control_program_builder import (
    OperationLibrarySnapshot,
    OperationTypeDefinition,
    load_operation_library_snapshot,
)
from app.services.preprocessor.geometry import GeneratedGeometry, GeometryBuilder
from app.services.preprocessor.legacy_surface_mesh import (
    LegacySurfaceMeshBuilder,
    LegacySurfacePair,
)
from app.services.preprocessor.prolongation import (
    ProlongationMathError,
    calculate_prolongation,
)
from app.services.preprocessor.surface_mesh import SurfaceMesh, SurfaceMeshError
from app.services.preprocessor.cutting import CuttingMathError, calculate_cutting
from app.services.preprocessor.upsetting import (
    DieDimensions,
    PressModeParameters,
    UpsettingMathError,
    calculate_upsetting,
)
from app.services.preprocessor.operation_keys import (
    AXIAL_PROLONGATION_TEMPLATE_IDS,
    CUTTING_TEMPLATE_IDS,
    FULL_DIE_TEMPLATE_IDS,
    FURNACE_TEMPLATE_ID,
    HEATING_TEMPERATURE_DURATION_TEMPLATE_ID,
    PROLONGATION_TEMPLATE_IDS,
    RADIAL_HEIGHT_BITES,
    RADIAL_INITIAL_ROTATIONS,
    RADIAL_PRESS_AXIS_FEED,
    RADIAL_ROTATION_HEIGHT_FEED,
    TRANSVERSAL_ROTATION_HEIGHT,
    UPSETTING_LENGTH_TARGET_TEMPLATE_IDS,
    UPSETTING_PRESSURE_CONTROL_TEMPLATE_IDS,
    UPSETTING_TAIL_FLATTENING,
    UPSETTING_TEMPLATE_IDS,
)


LOGGER = logging.getLogger(__name__)

FEED_DIRECTION_DEFAULT_ID = 2
FEED_DIRECTION_LEGACY_FIELD = "feed_direction_id"
FEED_DIRECTION_UPSETTING_FIELD = "feed_direction_upsetting_id"
FEED_DIRECTION_PROLONGATION_FIELD = "feed_direction_prolongation_id"
FEED_DIRECTION_TRANSVERSAL_COGGING_FIELD = "feed_direction_transversal_cogging_id"
FEED_DIRECTION_FIELDS = (
    FEED_DIRECTION_UPSETTING_FIELD,
    FEED_DIRECTION_PROLONGATION_FIELD,
    FEED_DIRECTION_TRANSVERSAL_COGGING_FIELD,
)
OLD_FORMING_SPEED_FIELDS = (
    "speed_upsetting",
    "speed_prolongation",
)
OPERATION_LOCAL_SPEED_FIELD = "speed"


class PreprocessorCompileError(ValueError):
    """Raised when document cards cannot be compiled into control-program rows."""

    def __init__(
        self,
        message: str,
        *,
        operation_id: int | None = None,
        document_operation_id: int | None = None,
        operation_template_id: str | None = None,
        source_block_id: object | None = None,
    ) -> None:
        self.message = message
        self.operation_id = operation_id
        self.document_operation_id = document_operation_id
        self.operation_template_id = operation_template_id
        self.source_block_id = source_block_id
        super().__init__(self._formatted_message())

    def with_card_context(self, card: "ProcessCard") -> "PreprocessorCompileError":
        """Return the same compile error enriched with source operation context."""

        if (
            self.operation_id is not None
            and self.document_operation_id is not None
            and self.operation_template_id is not None
            and self.source_block_id is not None
        ):
            return self
        return PreprocessorCompileError(
            self.message,
            operation_id=self.operation_id or card.operation_id,
            document_operation_id=self.document_operation_id or card.document_operation_id,
            operation_template_id=self.operation_template_id or card.operation_template_id,
            source_block_id=self.source_block_id or card.source_block_id,
        )

    def _formatted_message(self) -> str:
        parts = [self.message]
        context: list[str] = []
        if self.operation_id is not None:
            context.append(f"operation_id={self.operation_id}")
        if self.document_operation_id is not None:
            context.append(f"document_operation_id={self.document_operation_id}")
        if self.operation_template_id:
            context.append(f"operation_template_id={self.operation_template_id}")
        if self.source_block_id is not None:
            context.append(f"source_block_id={self.source_block_id}")
        if context:
            parts.append(f"({' '.join(context)})")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class ProcessCard:
    """User-facing process card normalized for the first compiler slice."""

    operation_id: int
    type_id: int | None = None
    parameters: Mapping[str, object] = field(default_factory=dict)
    document_operation_id: int | None = None
    operation_template_id: str | None = None
    operation_kind: str | None = None
    operation_label: str | None = None
    source_block_id: object | None = None
    press_id: int | None = None
    press_mode_id: int | None = None
    die_assembly_id: int | None = None
    top_die_id: int | None = None
    bottom_die_id: int | None = None
    material_id: int | None = None
    material_label: str | None = None
    weight_kg: float | None = None
    volume_mm3: float | None = None


@dataclass(frozen=True, slots=True)
class CompiledControlProgramRow:
    """One compiled row in the control program."""

    sequence_index: int
    simulation_index: int | None
    operation_id: int
    source_block_id: object | None
    type_id: int | None
    parent_type_id: str | None
    process_name: str
    library_name: str
    operation_type: str
    deformation_control: str
    step_control: str | None
    parameter_values: dict[str, object]
    control_parameters: dict[str, object]
    operation_specific_parameters: dict[str, object]
    is_geometry: bool
    press_id: int | None
    press_mode_id: int | None
    material_id: int | None
    material_label: str | None
    weight_kg: float | None
    duration_seconds: float | None
    total_time_seconds: float
    temperature_initial_c: float | None
    temperature_final_c: float | None
    time_before_operation_seconds: float | None
    simulation_expected_duration_days: float | None
    initial_geometry: GeneratedGeometry | None
    final_geometry: GeneratedGeometry | None
    initial_surface_area_mm2: float | None
    final_surface_area_mm2: float | None
    initial_surface_mesh: SurfaceMesh | None = None
    final_surface_mesh: SurfaceMesh | None = None
    metrics: dict[str, object] = field(default_factory=dict)
    compiler_notes: tuple[str, ...] = ()
    document_operation_id: int | None = None
    operation_template_id: str | None = None
    operation_kind: str | None = None
    operation_label: str | None = None


@dataclass(frozen=True, slots=True)
class CompiledControlProgram:
    """Compiled preprocessing output for one immutable document snapshot."""

    rows: tuple[CompiledControlProgramRow, ...]
    type_tree: dict[str, dict[str, Any]]
    flattened_type_ids: tuple[str, ...]


class PreprocessorCompiler:
    """Compile operation cards into initial control-program rows."""

    def __init__(self, *, geometry_builder: GeometryBuilder | None = None) -> None:
        self._geometry_builder = geometry_builder or GeometryBuilder()
        self._surface_builder = LegacySurfaceMeshBuilder()

    def compile(
        self,
        cards: Sequence[ProcessCard],
        library_snapshot: OperationLibrarySnapshot,
        *,
        default_press_id: int = 2,
    ) -> CompiledControlProgram:
        compiled_rows = tuple(
            self.iter_compile(
                cards,
                library_snapshot,
                default_press_id=default_press_id,
            )
        )
        return CompiledControlProgram(
            rows=compiled_rows,
            type_tree=library_snapshot.type_tree,
            flattened_type_ids=tuple(row.operation_template_id or "" for row in compiled_rows),
        )

    def iter_compile(
        self,
        cards: Sequence[ProcessCard],
        library_snapshot: OperationLibrarySnapshot,
        *,
        default_press_id: int = 2,
    ) -> Iterator[CompiledControlProgramRow]:
        """Yield compiled rows one by one.

        The compiler state is still sequential because every row may depend on
        the previous row geometry and accumulated process parameters. Yielding
        each completed row lets the runtime persist useful diagnostics before a
        later row fails.
        """

        previous_row: CompiledControlProgramRow | None = None
        simulation_index = 0
        accumulated_parameters: dict[str, object] = {}

        for sequence_index, card in enumerate(cards):
            try:
                LOGGER.info(
                    "Pre compile row started operation_id=%s document_operation_id=%s operation_template_id=%s",
                    card.operation_id,
                    card.document_operation_id,
                    card.operation_template_id,
                )
                operation = library_snapshot.get_operation(
                    card.operation_template_id,
                    type_id=card.type_id,
                )
                effective_card = self._with_accumulated_parameters(card, accumulated_parameters)
                parameter_values = self._extract_parameter_values(effective_card, operation)
                control_parameters = self._extract_control_parameters(effective_card, operation)
                simulation_row_index = simulation_index

                row = self._compile_row(
                    card=effective_card,
                    operation=operation,
                    sequence_index=sequence_index,
                    simulation_index=simulation_row_index,
                    parameter_values=parameter_values,
                    control_parameters=control_parameters,
                    previous_row=previous_row,
                    library_snapshot=library_snapshot,
                    default_press_id=default_press_id,
                )
                row = self._attach_card_metadata(row, effective_card)

                simulation_index += 1
                if operation.is_accumulate:
                    self._accumulate_parameters(accumulated_parameters, card)
                previous_row = row
                LOGGER.info(
                    "Pre compile row finished operation_id=%s document_operation_id=%s operation_template_id=%s operation_type=%s",
                    card.operation_id,
                    card.document_operation_id,
                    card.operation_template_id,
                    row.operation_type,
                )
                yield row
            except Exception as exc:
                wrapped = self._wrap_card_compile_error(exc, card)
                LOGGER.error(
                    "Pre compile row failed operation_id=%s document_operation_id=%s operation_template_id=%s: %s",
                    card.operation_id,
                    card.document_operation_id,
                    card.operation_template_id,
                    wrapped,
                    exc_info=LOGGER.isEnabledFor(logging.DEBUG),
                )
                raise wrapped from exc

    def _wrap_card_compile_error(
        self,
        exc: Exception,
        card: ProcessCard,
    ) -> PreprocessorCompileError:
        if isinstance(exc, PreprocessorCompileError):
            return exc.with_card_context(card)
        return PreprocessorCompileError(
            str(exc),
            operation_id=card.operation_id,
            document_operation_id=card.document_operation_id,
            operation_template_id=card.operation_template_id,
            source_block_id=card.source_block_id,
        )

    def compile_from_database(
        self,
        *,
        session: Session,
        cards: Sequence[ProcessCard],
        default_press_id: int = 2,
    ) -> CompiledControlProgram:
        """Load the library snapshot from the database and compile cards."""

        snapshot = load_operation_library_snapshot(session)
        enriched_cards = self._enrich_cards_from_database(
            session=session,
            cards=cards,
            library_snapshot=snapshot,
            default_press_id=default_press_id,
        )
        return self.compile(enriched_cards, snapshot, default_press_id=default_press_id)

    def iter_compile_from_database(
        self,
        *,
        session: Session,
        cards: Sequence[ProcessCard],
        default_press_id: int = 2,
    ) -> Iterator[CompiledControlProgramRow]:
        """Load database-backed metadata and yield compiled rows incrementally."""

        snapshot = load_operation_library_snapshot(session)
        enriched_cards = self._enrich_cards_from_database(
            session=session,
            cards=cards,
            library_snapshot=snapshot,
            default_press_id=default_press_id,
        )
        yield from self.iter_compile(
            enriched_cards,
            snapshot,
            default_press_id=default_press_id,
        )

    def _enrich_cards_from_database(
        self,
        *,
        session: Session,
        cards: Sequence[ProcessCard],
        library_snapshot: OperationLibrarySnapshot,
        default_press_id: int,
    ) -> tuple[ProcessCard, ...]:
        die_cache: dict[int, Die | None] = {}
        assembly_cache: dict[int, DieAssembly | None] = {}
        press_mode_cache: dict[int, PressMode | None] = {}
        default_press_mode_cache: dict[int, PressMode | None] = {}
        material_cache: dict[int, Material | None] = {}

        enriched_cards: list[ProcessCard] = []
        for card in cards:
            operation = library_snapshot.get_operation(
                card.operation_template_id,
                type_id=card.type_id,
            )
            parameters = dict(card.parameters)

            die_assembly_id = self._first_optional_int(
                card.die_assembly_id,
                parameters.get("die_assembly_id"),
            )
            top_die_id = self._first_optional_int(card.top_die_id, parameters.get("top_die_id"))
            bottom_die_id = self._first_optional_int(card.bottom_die_id, parameters.get("bottom_die_id"))
            if (top_die_id is None or bottom_die_id is None) and die_assembly_id is not None:
                assembly = self._get_die_assembly(session, assembly_cache, die_assembly_id)
                if assembly is not None:
                    top_die_id = top_die_id if top_die_id is not None else assembly.top_die_id
                    bottom_die_id = bottom_die_id if bottom_die_id is not None else assembly.bottom_die_id

            if top_die_id is not None:
                parameters["top_die_id"] = top_die_id
                parameters.setdefault(
                    "top_die_dimensions",
                    self._die_properties(self._get_die(session, die_cache, top_die_id)),
                )
            if bottom_die_id is not None:
                parameters["bottom_die_id"] = bottom_die_id
                parameters.setdefault(
                    "bottom_die_dimensions",
                    self._die_properties(self._get_die(session, die_cache, bottom_die_id)),
                )

            fallback_press_id = default_press_id if operation is not None else None
            press_id = self._first_optional_int(card.press_id, parameters.get("press_id"), fallback_press_id)
            press_mode_id = self._first_optional_int(card.press_mode_id, parameters.get("press_mode_id"))
            press_mode: PressMode | None = None
            if press_mode_id is None and press_id is not None:
                press_mode = self._get_default_press_mode(session, default_press_mode_cache, press_id)
                if press_mode is not None:
                    press_mode_id = press_mode.id
            elif press_mode_id is not None:
                press_mode = self._get_press_mode(session, press_mode_cache, press_mode_id)

            if press_mode is not None:
                press_mode_id = press_mode.id
                press_id = self._first_optional_int(press_id, press_mode.press_id)
                parameters.setdefault("press_mode_properties", dict(press_mode.properties or {}))
            if press_mode_id is not None:
                parameters["press_mode_id"] = press_mode_id

            material_label = card.material_label
            if material_label is None and card.material_id is not None:
                material = self._get_material(session, material_cache, card.material_id)
                if material is not None:
                    material_label = material.name

            enriched_cards.append(
                ProcessCard(
                    operation_id=card.operation_id,
                    type_id=card.type_id,
                    parameters=parameters,
                    document_operation_id=card.document_operation_id,
                    operation_template_id=card.operation_template_id,
                    operation_kind=card.operation_kind,
                    operation_label=card.operation_label,
                    source_block_id=card.source_block_id,
                    press_id=press_id,
                    press_mode_id=press_mode_id,
                    die_assembly_id=die_assembly_id,
                    top_die_id=top_die_id,
                    bottom_die_id=bottom_die_id,
                    material_id=card.material_id,
                    material_label=material_label,
                    weight_kg=card.weight_kg,
                    volume_mm3=card.volume_mm3,
                )
            )

        return tuple(enriched_cards)

    def _attach_card_metadata(
        self,
        row: CompiledControlProgramRow,
        card: ProcessCard,
    ) -> CompiledControlProgramRow:
        return replace(
            row,
            document_operation_id=card.document_operation_id,
            operation_template_id=card.operation_template_id,
            operation_kind=card.operation_kind,
            operation_label=card.operation_label,
        )

    def _get_die(self, session: Session, cache: dict[int, Die | None], die_id: int) -> Die | None:
        if die_id not in cache:
            cache[die_id] = session.get(Die, die_id)
        return cache[die_id]

    def _get_die_assembly(
        self,
        session: Session,
        cache: dict[int, DieAssembly | None],
        die_assembly_id: int,
    ) -> DieAssembly | None:
        if die_assembly_id not in cache:
            cache[die_assembly_id] = session.get(DieAssembly, die_assembly_id)
        return cache[die_assembly_id]

    def _get_press_mode(
        self,
        session: Session,
        cache: dict[int, PressMode | None],
        press_mode_id: int,
    ) -> PressMode | None:
        if press_mode_id not in cache:
            cache[press_mode_id] = session.get(PressMode, press_mode_id)
        return cache[press_mode_id]

    def _get_default_press_mode(
        self,
        session: Session,
        cache: dict[int, PressMode | None],
        press_id: int,
    ) -> PressMode | None:
        if press_id not in cache:
            stmt = (
                select(PressMode)
                .where(PressMode.press_id == press_id, PressMode.is_obsolete.is_(False))
                .order_by(PressMode.is_default_press_mode.desc(), PressMode.id.asc())
            )
            cache[press_id] = session.scalars(stmt).first()
        return cache[press_id]

    def _get_material(
        self,
        session: Session,
        cache: dict[int, Material | None],
        material_id: int,
    ) -> Material | None:
        if material_id not in cache:
            cache[material_id] = session.get(Material, material_id)
        return cache[material_id]

    def _die_properties(self, die: Die | None) -> dict[str, object] | None:
        if die is None or die.properties is None:
            return None
        return dict(die.properties)

    def _compile_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
        default_press_id: int,
    ) -> CompiledControlProgramRow:
        if operation.is_geometry:
            return self._compile_billet_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
            )
        if operation.operation_template_id == FURNACE_TEMPLATE_ID:
            return self._compile_furnace_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
                previous_row=previous_row,
            )
        if operation.operation_template_id == HEATING_TEMPERATURE_DURATION_TEMPLATE_ID:
            return self._compile_heat_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
                previous_row=previous_row,
            )
        if operation.operation_template_id in UPSETTING_TEMPLATE_IDS:
            return self._compile_upsetting_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
                previous_row=previous_row,
                library_snapshot=library_snapshot,
                default_press_id=default_press_id,
            )
        if operation.operation_template_id in PROLONGATION_TEMPLATE_IDS:
            return self._compile_prolongation_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
                previous_row=previous_row,
                library_snapshot=library_snapshot,
                default_press_id=default_press_id,
            )
        if operation.operation_template_id == RADIAL_INITIAL_ROTATIONS:
            return self._compile_radial_initial_rotations_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
                previous_row=previous_row,
                library_snapshot=library_snapshot,
            )
        if operation.operation_template_id in CUTTING_TEMPLATE_IDS:
            return self._compile_cutting_row(
                card=card,
                operation=operation,
                sequence_index=sequence_index,
                simulation_index=simulation_index,
                parameter_values=parameter_values,
                control_parameters=control_parameters,
                previous_row=previous_row,
                library_snapshot=library_snapshot,
            )
        return self._compile_generic_row(
            card=card,
            operation=operation,
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            previous_row=previous_row,
            library_snapshot=library_snapshot,
            default_press_id=default_press_id,
        )

    def _extract_parameter_values(
        self,
        card: ProcessCard,
        operation: OperationTypeDefinition,
    ) -> dict[str, object]:
        values: dict[str, object] = {}
        for name in operation.db_column_names:
            values[name] = card.parameters.get(name)
        return values

    def _extract_control_parameters(
        self,
        card: ProcessCard,
        operation: OperationTypeDefinition,
    ) -> dict[str, object]:
        return {
            key: value
            for key, value in card.parameters.items()
            if key not in operation.db_column_names
        }

    def _with_accumulated_parameters(
        self,
        card: ProcessCard,
        accumulated_parameters: Mapping[str, object],
    ) -> ProcessCard:
        if not accumulated_parameters:
            return card

        parameters = dict(accumulated_parameters)
        local_parameters = dict(card.parameters)
        if (
            "press_id" in accumulated_parameters
            and self._coerce_optional_int(card.parameters.get("press_id")) is None
        ):
            local_parameters.pop("press_mode_id", None)
            local_parameters.pop("press_mode_properties", None)
        parameters.update(local_parameters)
        return ProcessCard(
            operation_id=card.operation_id,
            type_id=card.type_id,
            parameters=parameters,
            document_operation_id=card.document_operation_id,
            operation_template_id=card.operation_template_id,
            operation_kind=card.operation_kind,
            operation_label=card.operation_label,
            source_block_id=card.source_block_id,
            press_id=self._first_optional_int(parameters.get("press_id"), card.press_id),
            press_mode_id=self._first_optional_int(parameters.get("press_mode_id"), card.press_mode_id),
            die_assembly_id=self._first_optional_int(parameters.get("die_assembly_id"), card.die_assembly_id),
            top_die_id=self._first_optional_int(parameters.get("top_die_id"), card.top_die_id),
            bottom_die_id=self._first_optional_int(parameters.get("bottom_die_id"), card.bottom_die_id),
            material_id=self._first_optional_int(parameters.get("material_id"), card.material_id),
            material_label=card.material_label,
            weight_kg=card.weight_kg,
            volume_mm3=card.volume_mm3,
        )

    def _accumulate_parameters(
        self,
        accumulated_parameters: dict[str, object],
        card: ProcessCard,
    ) -> None:
        accumulated_parameters.update(card.parameters)
        if card.press_id is not None:
            accumulated_parameters["press_id"] = card.press_id
        if card.press_mode_id is not None:
            accumulated_parameters["press_mode_id"] = card.press_mode_id
        if card.die_assembly_id is not None:
            accumulated_parameters["die_assembly_id"] = card.die_assembly_id
        if card.top_die_id is not None:
            accumulated_parameters["top_die_id"] = card.top_die_id
        if card.bottom_die_id is not None:
            accumulated_parameters["bottom_die_id"] = card.bottom_die_id

    def _build_geometry_if_needed(
        self,
        card: ProcessCard,
        operation: OperationTypeDefinition,
    ) -> GeneratedGeometry | None:
        if not operation.is_geometry:
            return None
        if card.type_id is None:
            raise PreprocessorCompileError(
                f"Geometry card operation_id={card.operation_id} requires geometry type_id"
            )
        if card.volume_mm3 is None:
            raise PreprocessorCompileError(
                f"Geometry card operation_id={card.operation_id} requires volume_mm3"
            )
        return self._geometry_builder.build(
            type_id=card.type_id,
            parameters=card.parameters,
            volume_mm3=card.volume_mm3,
        )

    def _compile_billet_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
    ) -> CompiledControlProgramRow:
        geometry = self._build_geometry_if_needed(card, operation)
        assert geometry is not None
        surface_area = self._surface_area_mm2(geometry)
        step_control = card.material_label or control_parameters.get("material_short_name")
        metrics: dict[str, object] = {}
        surface_pair = self._safe_surface_pair("billet", lambda: self._surface_builder.billet(geometry))
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)
        mesh_elements = self._coerce_optional_int(card.parameters.get("mesh_elements"))
        if mesh_elements is not None:
            metrics["mesh_elements"] = mesh_elements
        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type="NewBillet",
            deformation_control="NA",
            step_control=str(step_control) if step_control is not None else None,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters={},
            is_geometry=operation.is_geometry,
            press_id=card.press_id,
            press_mode_id=card.press_mode_id,
            material_id=card.material_id,
            material_label=card.material_label,
            weight_kg=card.weight_kg,
            duration_seconds=0.0,
            total_time_seconds=0.0,
            temperature_initial_c=None,
            temperature_final_c=None,
            time_before_operation_seconds=0.0,
            simulation_expected_duration_days=0.0,
            initial_geometry=geometry,
            final_geometry=geometry,
            initial_surface_area_mm2=surface_area,
            final_surface_area_mm2=surface_area,
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
        )

    def _compile_furnace_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
    ) -> CompiledControlProgramRow:
        previous = self._require_previous_row(previous_row, card, "furnace")
        final_geometry = self._require_geometry(previous.final_geometry, card, "furnace")
        furnace_class_id = self._optional_int_parameter(card, "furnace_class_id")
        furnace_temperature = self._first_optional_float(card, "temperature")
        if furnace_temperature is None:
            furnace_temperature = self._last_program_temperature(card.parameters.get("temperature_program"))
        if furnace_temperature is None:
            raise PreprocessorCompileError(
                f"Furnace card operation_id={card.operation_id} requires numeric parameter 'temperature' "
                "or at least one hold row with temperature_c in temperature_program"
            )
        operation_specific_parameters: dict[str, object] = {
            "furnace_class_id": furnace_class_id,
            "control_temperature_furnace_initial_c": previous.temperature_final_c,
            "control_temperature_furnace_final_c": furnace_temperature,
        }
        surface_pair = self._safe_surface_pair(
            "furnace",
            lambda: self._surface_builder.static(previous.final_surface_mesh),
        )
        metrics = dict(previous.metrics)
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type="Furnace",
            deformation_control="NA",
            step_control=previous.step_control,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters=operation_specific_parameters,
            is_geometry=operation.is_geometry,
            press_id=previous.press_id,
            press_mode_id=previous.press_mode_id,
            material_id=previous.material_id,
            material_label=previous.material_label,
            weight_kg=previous.weight_kg,
            duration_seconds=0.0,
            total_time_seconds=previous.total_time_seconds,
            temperature_initial_c=previous.temperature_final_c,
            temperature_final_c=furnace_temperature,
            time_before_operation_seconds=0.0,
            simulation_expected_duration_days=0.0,
            initial_geometry=final_geometry,
            final_geometry=final_geometry,
            initial_surface_area_mm2=previous.final_surface_area_mm2,
            final_surface_area_mm2=previous.final_surface_area_mm2,
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
        )

    def _compile_heat_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
    ) -> CompiledControlProgramRow:
        previous = self._require_previous_row(previous_row, card, "heating")
        final_geometry = self._require_geometry(previous.final_geometry, card, "heating")
        duration_minutes = self._get_float_parameter(card, "duration")
        duration_seconds = duration_minutes * 60.0
        furnace_class_id = self._first_optional_int(
            card.parameters.get("furnace_class_id"),
            control_parameters.get("furnace_class_id"),
            previous.control_parameters.get("furnace_class_id"),
            previous.operation_specific_parameters.get("furnace_class_id"),
        )
        next_temperature = self._get_float_parameter(card, "temperature")
        initial_temperature = previous.temperature_final_c

        operation_specific_parameters: dict[str, object] = {
            "furnace_class_id": furnace_class_id,
            "control_duration_seconds": duration_seconds,
            "control_temperature_furnace_initial_c": initial_temperature,
            "control_temperature_furnace_final_c": next_temperature,
        }
        surface_pair = self._safe_surface_pair(
            "heating",
            lambda: self._surface_builder.static(previous.final_surface_mesh),
        )
        metrics = dict(previous.metrics)
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type="Heat",
            deformation_control="NA",
            step_control=previous.step_control,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters=operation_specific_parameters,
            is_geometry=operation.is_geometry,
            press_id=previous.press_id,
            press_mode_id=previous.press_mode_id,
            material_id=previous.material_id,
            material_label=previous.material_label,
            weight_kg=previous.weight_kg,
            duration_seconds=duration_seconds,
            total_time_seconds=previous.total_time_seconds + duration_seconds,
            temperature_initial_c=initial_temperature,
            temperature_final_c=next_temperature,
            time_before_operation_seconds=0.0,
            simulation_expected_duration_days=0.0,
            initial_geometry=final_geometry,
            final_geometry=final_geometry,
            initial_surface_area_mm2=previous.final_surface_area_mm2,
            final_surface_area_mm2=previous.final_surface_area_mm2,
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
        )

    def _compile_upsetting_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
        default_press_id: int,
    ) -> CompiledControlProgramRow:
        previous = self._require_previous_row(previous_row, card, "upsetting")
        initial_geometry = self._require_geometry(previous.final_geometry, card, "upsetting")
        resolved_press_id = self._first_optional_int(card.press_id, previous.press_id, default_press_id)
        resolved_press_mode_id = self._first_optional_int(
            card.press_mode_id,
            self._coerce_optional_int(control_parameters.get("press_mode_id")),
            previous.press_mode_id,
        )
        time_before = self._resolve_time_between_operations(
            card=card,
            operation=operation,
            previous_row=previous,
            library_snapshot=library_snapshot,
            press_mode_id=resolved_press_mode_id,
        )
        top_die = self._resolve_die_dimensions(
            card=card,
            side="top",
            control_parameters=control_parameters,
            operation_family="Upsetting",
        )
        bottom_die = self._resolve_die_dimensions(
            card=card,
            side="bottom",
            control_parameters=control_parameters,
            operation_family="Upsetting",
        )
        press_mode = self._resolve_press_mode_parameters(
            card=card,
            control_parameters=control_parameters,
            default_id=resolved_press_mode_id,
            operation_family="Upsetting",
        )
        target_speed = self._resolve_speed_mm_per_s(
            card=card,
            operation=operation,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            press_mode=press_mode,
        )
        angle_deg = self._first_float_parameter(card, "angle", default=0.0)
        current_feed_direction_id = self._resolve_feed_direction_id(card=card, operation=operation)
        previous_feed_direction_id = self._resolve_previous_feed_direction_id(previous, operation)
        operation_template_id = operation.operation_template_id

        final_length_input_mm: float | None = None
        stroke_mm: float | None = None
        if operation_template_id in UPSETTING_LENGTH_TARGET_TEMPLATE_IDS:
            final_length_input_mm = self._first_float_parameter(
                card,
                "height",
                "final_length",
                "length",
            )
        elif operation_template_id == UPSETTING_TAIL_FLATTENING:
            stroke_mm = self._first_float_parameter(card, "stroke", "penetration")

        try:
            upsetting_result = calculate_upsetting(
                template_id=operation_template_id,
                initial_geometry=initial_geometry,
                press_mode=press_mode,
                top_die=top_die,
                bottom_die=bottom_die,
                speed_mm_per_s=target_speed,
                previous_total_time_seconds=previous.total_time_seconds,
                time_between_operation_seconds=time_before,
                angle_deg=angle_deg,
                final_length_input_mm=final_length_input_mm,
                stroke_mm=stroke_mm,
                is_same_operation_type_as_previous=previous.operation_type == "Upset",
                current_feed_direction_id=current_feed_direction_id,
                previous_feed_direction_id=previous_feed_direction_id,
                mesh_elements=self._resolve_mesh_elements(card, previous),
            )
        except UpsettingMathError as exc:
            raise PreprocessorCompileError(
                f"Upsetting card operation_id={card.operation_id} cannot be compiled: {exc}"
            ) from exc

        deformation_control = "P" if operation_template_id in UPSETTING_PRESSURE_CONTROL_TEMPLATE_IDS else "H"
        operation_specific_parameters = {
            **control_parameters,
            **upsetting_result.operation_specific_parameters,
            "raw_parameters": dict(card.parameters),
            "radial_rotations": [("x", angle_deg), ("y", 90.0)],
            "deformation_geometry_ported": True,
        }
        metrics = dict(upsetting_result.metrics)
        self._store_feed_direction_metrics(metrics, operation, current_feed_direction_id)
        surface_pair = self._safe_surface_pair(
            "upsetting",
            lambda: self._surface_builder.upsetting(
                previous_final=previous.final_surface_mesh,
                initial_geometry=initial_geometry,
                final_geometry=upsetting_result.final_geometry,
                metrics=metrics,
                operation_specific_parameters=operation_specific_parameters,
                template_id=operation.operation_template_id,
            ),
        )
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)

        notes = list(upsetting_result.compiler_notes)
        if upsetting_result.simulation_expected_duration_days is None:
            notes.append("Simulation expected duration estimate is not ported yet.")
        duration_seconds = upsetting_result.total_time_seconds - previous.total_time_seconds

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type="Upset",
            deformation_control=deformation_control,
            step_control=self._infer_step_control(operation),
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters=operation_specific_parameters,
            is_geometry=operation.is_geometry,
            press_id=resolved_press_id,
            press_mode_id=press_mode.press_mode_id,
            material_id=previous.material_id,
            material_label=previous.material_label,
            weight_kg=previous.weight_kg,
            duration_seconds=duration_seconds,
            total_time_seconds=upsetting_result.total_time_seconds,
            temperature_initial_c=previous.temperature_final_c,
            temperature_final_c=previous.temperature_final_c,
            time_before_operation_seconds=upsetting_result.time_before_operation_seconds,
            simulation_expected_duration_days=upsetting_result.simulation_expected_duration_days,
            initial_geometry=initial_geometry,
            final_geometry=upsetting_result.final_geometry,
            initial_surface_area_mm2=upsetting_result.metrics.get("initial_surface_area_mm2"),
            final_surface_area_mm2=upsetting_result.metrics.get("final_surface_area_mm2"),
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
            compiler_notes=tuple(notes),
        )

    def _compile_prolongation_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
        default_press_id: int,
    ) -> CompiledControlProgramRow:
        previous = self._require_previous_row(previous_row, card, "prolongation")
        initial_geometry = self._require_geometry(previous.final_geometry, card, "prolongation")
        resolved_press_id = self._first_optional_int(card.press_id, previous.press_id, default_press_id)
        resolved_press_mode_id = self._first_optional_int(
            card.press_mode_id,
            self._coerce_optional_int(control_parameters.get("press_mode_id")),
            previous.press_mode_id,
        )
        time_before = self._resolve_time_between_operations(
            card=card,
            operation=operation,
            previous_row=previous,
            library_snapshot=library_snapshot,
            press_mode_id=resolved_press_mode_id,
        )
        top_die = self._resolve_die_dimensions(
            card=card,
            side="top",
            control_parameters=control_parameters,
            operation_family="Prolongation",
        )
        bottom_die = self._resolve_die_dimensions(
            card=card,
            side="bottom",
            control_parameters=control_parameters,
            operation_family="Prolongation",
        )
        press_mode = self._resolve_press_mode_parameters(
            card=card,
            control_parameters=control_parameters,
            default_id=resolved_press_mode_id,
            operation_family="Prolongation",
        )
        target_speed = self._resolve_speed_mm_per_s(
            card=card,
            operation=operation,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            press_mode=press_mode,
        )
        angle_deg = self._resolve_prolongation_angle(card)
        current_feed_direction_id = self._resolve_feed_direction_id(card=card, operation=operation)
        previous_feed_direction_id = self._resolve_previous_feed_direction_id(previous, operation)
        compiled_operation_type = "FullDie" if operation.deformation_type == "full_die" else "Draw"

        try:
            result = calculate_prolongation(
                template_id=operation.operation_template_id,
                initial_geometry=initial_geometry,
                press_mode=press_mode,
                top_die=top_die,
                bottom_die=bottom_die,
                speed_mm_per_s=target_speed,
                previous_total_time_seconds=previous.total_time_seconds,
                time_between_operation_seconds=time_before,
                angle_deg=angle_deg,
                final_height_mm=self._first_optional_float(card, "height", "final_height"),
                final_diameter_mm=self._first_optional_float(card, "diameter", "final_diameter"),
                radial_feed_mm=self._first_optional_float(card, "radial_feed"),
                feed_mm=self._first_optional_float(card, "feed", "feed_first"),
                feed_first_mm=self._first_optional_float(card, "feed_first"),
                feed_middle_mm=self._first_optional_float(card, "feed_middle"),
                feed_last_mm=self._first_optional_float(card, "feed_last"),
                num_of_bites_input=self._coerce_optional_int(card.parameters.get("num_of_bites")),
                skip_bites=self._parse_skip_bites(card.parameters.get("skip_bites")),
                rotation_per_bite_deg=self._first_optional_float(card, "rotation_per_bite") or 0.0,
                current_feed_direction_id=current_feed_direction_id,
                previous_feed_direction_id=previous_feed_direction_id,
                is_same_operation_type_as_previous=previous.operation_type == compiled_operation_type,
                mesh_elements=self._resolve_mesh_elements(card, previous),
                extra_rotations={
                    "y_rotation": self._first_optional_float(card, "y_rotation") or 0.0,
                    "z_rotation": self._first_optional_float(card, "z_rotation") or 0.0,
                },
            )
        except ProlongationMathError as exc:
            raise PreprocessorCompileError(
                f"Prolongation card operation_id={card.operation_id} cannot be compiled: {exc}"
            ) from exc

        operation_specific_parameters = {
            **control_parameters,
            **result.operation_specific_parameters,
            "raw_parameters": dict(card.parameters),
            "deformation_geometry_ported": True,
        }
        metrics = dict(result.metrics)
        self._store_feed_direction_metrics(metrics, operation, current_feed_direction_id)
        surface_pair = self._safe_surface_pair(
            "prolongation",
            lambda: self._surface_builder.prolongation(
                previous_final=previous.final_surface_mesh,
                initial_geometry=initial_geometry,
                final_geometry=result.final_geometry,
                metrics=metrics,
                operation_specific_parameters=operation_specific_parameters,
                template_id=operation.operation_template_id,
            ),
        )
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)

        notes = list(result.compiler_notes)
        if result.simulation_expected_duration_days is None:
            notes.append("Simulation expected duration estimate is not ported yet.")
        duration_seconds = result.total_time_seconds - previous.total_time_seconds

        mesh_elements = self._coerce_optional_int(card.parameters.get("mesh_elements"))
        if mesh_elements is not None:
            metrics["mesh_elements"] = mesh_elements

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type=compiled_operation_type,
            deformation_control="H",
            step_control=self._infer_step_control(operation),
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters=operation_specific_parameters,
            is_geometry=operation.is_geometry,
            press_id=resolved_press_id,
            press_mode_id=press_mode.press_mode_id,
            material_id=previous.material_id,
            material_label=previous.material_label,
            weight_kg=previous.weight_kg,
            duration_seconds=duration_seconds,
            total_time_seconds=result.total_time_seconds,
            temperature_initial_c=previous.temperature_final_c,
            temperature_final_c=previous.temperature_final_c,
            time_before_operation_seconds=result.time_before_operation_seconds,
            simulation_expected_duration_days=result.simulation_expected_duration_days,
            initial_geometry=initial_geometry,
            final_geometry=result.final_geometry,
            initial_surface_area_mm2=result.metrics.get("initial_surface_area_mm2"),
            final_surface_area_mm2=result.metrics.get("final_surface_area_mm2"),
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
            compiler_notes=tuple(notes),
        )

    def _compile_radial_initial_rotations_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
    ) -> CompiledControlProgramRow:
        previous = self._require_previous_row(previous_row, card, "radial initial rotations")
        geometry = self._require_geometry(previous.final_geometry, card, "radial initial rotations")
        time_before = self._resolve_time_between_operations(
            card=card,
            operation=operation,
            previous_row=previous,
            library_snapshot=library_snapshot,
            press_mode_id=previous.press_mode_id,
        ) or 0.0
        rotations = (
            ("x", self._first_float_parameter(card, "rotation_1_x", default=0.0)),
            ("y", self._first_float_parameter(card, "rotation_2_y", default=0.0)),
            ("x", self._first_float_parameter(card, "rotation_3_x", default=0.0)),
            ("y", self._first_float_parameter(card, "rotation_4_y", default=0.0)),
        )
        total_time_seconds = previous.total_time_seconds + time_before
        metrics = dict(previous.metrics)
        metrics.update(
            {
                "radial_initial_rotations": rotations,
                "time_before_pass_seconds": time_before,
            }
        )
        surface_pair = self._safe_surface_pair(
            "radial initial rotations",
            lambda: self._surface_builder.static(previous.final_surface_mesh),
        )
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)
        operation_specific_parameters = {
            **control_parameters,
            "raw_parameters": dict(card.parameters),
            "radial_initial_rotations": rotations,
            "radial_rotations": rotations,
            "deformation_geometry_ported": True,
        }

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type="RadialInitialRotations",
            deformation_control="NA",
            step_control=self._infer_step_control(operation),
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters=operation_specific_parameters,
            is_geometry=operation.is_geometry,
            press_id=previous.press_id,
            press_mode_id=previous.press_mode_id,
            material_id=previous.material_id,
            material_label=previous.material_label,
            weight_kg=previous.weight_kg,
            duration_seconds=0.0,
            total_time_seconds=total_time_seconds,
            temperature_initial_c=previous.temperature_final_c,
            temperature_final_c=previous.temperature_final_c,
            time_before_operation_seconds=time_before,
            simulation_expected_duration_days=0.0,
            initial_geometry=geometry,
            final_geometry=geometry,
            initial_surface_area_mm2=previous.final_surface_area_mm2,
            final_surface_area_mm2=previous.final_surface_area_mm2,
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
        )

    def _compile_cutting_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
    ) -> CompiledControlProgramRow:
        previous = self._require_previous_row(previous_row, card, "cutting")
        initial_geometry = self._require_geometry(previous.final_geometry, card, "cutting")
        self._validate_explicit_speed_fields(
            card=card,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
        )
        time_before = self._resolve_time_between_operations(
            card=card,
            operation=operation,
            previous_row=previous,
            library_snapshot=library_snapshot,
            press_mode_id=previous.press_mode_id,
        )
        pieces_count = self._optional_int_parameter(card, "pieces_count")
        piece_number = self._optional_int_parameter(card, "piece_number")
        if pieces_count is None:
            raise PreprocessorCompileError(f"Cutting card operation_id={card.operation_id} requires pieces_count")
        if piece_number is None:
            raise PreprocessorCompileError(f"Cutting card operation_id={card.operation_id} requires piece_number")

        try:
            cutting_result = calculate_cutting(
                template_id=operation.operation_template_id,
                initial_geometry=initial_geometry,
                pieces_count=pieces_count,
                piece_number=piece_number,
                percentage_to_keep=self._first_float_parameter(card, "percentage_to_keep"),
                previous_total_time_seconds=previous.total_time_seconds,
                time_between_operation_seconds=time_before,
            )
        except CuttingMathError as exc:
            raise PreprocessorCompileError(
                f"Cutting card operation_id={card.operation_id} cannot be compiled: {exc}"
            ) from exc

        operation_specific_parameters = {
            **control_parameters,
            **cutting_result.operation_specific_parameters,
            "raw_parameters": dict(card.parameters),
        }
        speed_value = self._first_optional_float(card, "speed_prolongation", "speed")
        if speed_value is not None:
            operation_specific_parameters["speed_prolongation"] = speed_value
        metrics = dict(cutting_result.metrics)
        surface_pair = self._safe_surface_pair(
            "cutting",
            lambda: self._surface_builder.cutting(
                previous_final=previous.final_surface_mesh,
                final_geometry=cutting_result.final_geometry,
                template_id=operation.operation_template_id,
            ),
        )
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)

        notes = list(cutting_result.compiler_notes)
        if cutting_result.simulation_expected_duration_days is None:
            notes.append("Simulation expected duration estimate is not ported yet.")
        duration_seconds = cutting_result.total_time_seconds - previous.total_time_seconds

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type="Cut",
            deformation_control="P",
            step_control=self._infer_step_control(operation),
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters=operation_specific_parameters,
            is_geometry=operation.is_geometry,
            press_id=previous.press_id,
            press_mode_id=previous.press_mode_id,
            material_id=previous.material_id,
            material_label=previous.material_label,
            weight_kg=previous.weight_kg,
            duration_seconds=duration_seconds,
            total_time_seconds=cutting_result.total_time_seconds,
            temperature_initial_c=previous.temperature_final_c,
            temperature_final_c=previous.temperature_final_c,
            time_before_operation_seconds=cutting_result.time_before_operation_seconds,
            simulation_expected_duration_days=cutting_result.simulation_expected_duration_days,
            initial_geometry=initial_geometry,
            final_geometry=cutting_result.final_geometry,
            initial_surface_area_mm2=cutting_result.metrics.get("initial_surface_area_mm2"),
            final_surface_area_mm2=cutting_result.metrics.get("final_surface_area_mm2"),
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
            compiler_notes=tuple(notes),
        )

    def _compile_generic_row(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        sequence_index: int,
        simulation_index: int | None,
        parameter_values: dict[str, object],
        control_parameters: dict[str, object],
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
        default_press_id: int,
    ) -> CompiledControlProgramRow:
        previous_geometry = previous_row.final_geometry if previous_row is not None else None
        previous_surface_area = previous_row.final_surface_area_mm2 if previous_row is not None else None
        metrics = dict(previous_row.metrics or {}) if previous_row is not None else {}
        mesh_elements = self._coerce_optional_int(card.parameters.get("mesh_elements"))
        if mesh_elements is not None:
            metrics["mesh_elements"] = mesh_elements
        for feed_direction_field in FEED_DIRECTION_FIELDS:
            feed_direction_id = self._coerce_optional_int(card.parameters.get(feed_direction_field))
            if feed_direction_id is not None:
                metrics[feed_direction_field] = feed_direction_id
        legacy_feed_direction_id = self._coerce_optional_int(card.parameters.get(FEED_DIRECTION_LEGACY_FIELD))
        if legacy_feed_direction_id is not None:
            metrics[FEED_DIRECTION_LEGACY_FIELD] = legacy_feed_direction_id
        resolved_press_id = card.press_id
        resolved_press_mode_id = card.press_mode_id
        if resolved_press_id is None and previous_row is not None:
            resolved_press_id = previous_row.press_id
        if resolved_press_mode_id is None and previous_row is not None:
            resolved_press_mode_id = previous_row.press_mode_id
        if resolved_press_id is None:
            resolved_press_id = default_press_id

        time_before = self._resolve_time_between_operations(
            card=card,
            operation=operation,
            previous_row=previous_row,
            library_snapshot=library_snapshot,
            press_mode_id=resolved_press_mode_id,
        )

        notes: list[str] = []
        if not operation.is_geometry:
            notes.append("Control row compiled without operation-family-specific deformation math.")

        total_time_seconds = previous_row.total_time_seconds if previous_row is not None else 0.0
        temperature = previous_row.temperature_final_c if previous_row is not None else None
        surface_pair = self._safe_surface_pair(
            "generic",
            lambda: self._surface_builder.static(previous_row.final_surface_mesh if previous_row is not None else None),
        )
        if surface_pair.notes:
            metrics["legacy_surface_notes"] = list(surface_pair.notes)

        return CompiledControlProgramRow(
            sequence_index=sequence_index,
            simulation_index=simulation_index,
            operation_id=card.operation_id,
            source_block_id=card.source_block_id,
            type_id=card.type_id,
            parent_type_id=operation.parent_type_id,
            process_name=operation.process_name,
            library_name=operation.library_name,
            operation_type=operation.process_name,
            deformation_control="NA",
            step_control=self._infer_step_control(operation),
            parameter_values=parameter_values,
            control_parameters=control_parameters,
            operation_specific_parameters={"raw_parameters": dict(card.parameters)},
            is_geometry=operation.is_geometry,
            press_id=resolved_press_id,
            press_mode_id=resolved_press_mode_id,
            material_id=card.material_id if card.material_id is not None else (previous_row.material_id if previous_row else None),
            material_label=card.material_label if card.material_label is not None else (previous_row.material_label if previous_row else None),
            weight_kg=card.weight_kg if card.weight_kg is not None else (previous_row.weight_kg if previous_row else None),
            duration_seconds=None,
            total_time_seconds=total_time_seconds,
            temperature_initial_c=temperature,
            temperature_final_c=temperature,
            time_before_operation_seconds=time_before,
            simulation_expected_duration_days=None,
            initial_geometry=previous_geometry,
            final_geometry=previous_geometry,
            initial_surface_area_mm2=previous_surface_area,
            final_surface_area_mm2=previous_surface_area,
            initial_surface_mesh=surface_pair.initial,
            final_surface_mesh=surface_pair.final,
            metrics=metrics,
            compiler_notes=tuple(notes),
        )

    def _resolve_mesh_elements(
        self,
        card: ProcessCard,
        previous_row: CompiledControlProgramRow | None,
    ) -> int | None:
        """Use a local override, otherwise carry the title-level mesh setting forward."""

        mesh_elements = self._coerce_optional_int(card.parameters.get("mesh_elements"))
        if mesh_elements is not None:
            return mesh_elements
        if previous_row is None:
            return None
        return self._coerce_optional_int(previous_row.metrics.get("mesh_elements"))

    def _resolve_time_between_operations(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        previous_row: CompiledControlProgramRow | None,
        library_snapshot: OperationLibrarySnapshot,
        press_mode_id: int | None,
    ) -> float | None:
        if previous_row is None or press_mode_id is None:
            return None
        if not operation.operation_template_id or not previous_row.operation_template_id:
            return None
        try:
            return library_snapshot.get_time_between_operations(
                first_operation_template_id=operation.operation_template_id,
                second_operation_template_id=previous_row.operation_template_id,
                press_id=press_mode_id,
            )
        except Exception as exc:
            LOGGER.debug(
                "No time_between_operations record for operation_template_id=%s previous_operation_template_id=%s press_mode_id=%s: %s",
                operation.operation_template_id,
                previous_row.operation_template_id,
                press_mode_id,
                exc,
            )
            return None

    def _resolve_die_dimensions(
        self,
        *,
        card: ProcessCard,
        side: str,
        control_parameters: Mapping[str, object],
        operation_family: str = "Forming",
    ) -> DieDimensions:
        mapping_key = f"{side}_die_dimensions"
        raw_mapping = self._first_mapping(card.parameters.get(mapping_key), control_parameters.get(mapping_key))
        if raw_mapping is None:
            die_id = self._coerce_optional_int(card.parameters.get(f"{side}_die_id"))
            if side == "top":
                die_id = self._first_optional_int(card.top_die_id, die_id)
            else:
                die_id = self._first_optional_int(card.bottom_die_id, die_id)
            raise PreprocessorCompileError(
                f"{operation_family} card operation_id={card.operation_id} requires {mapping_key}; "
                f"resolved {side}_die_id={die_id!r}"
            )
        default_id = None
        if side == "top":
            default_id = self._first_optional_int(card.top_die_id, self._coerce_optional_int(card.parameters.get("top_die_id")))
        else:
            default_id = self._first_optional_int(card.bottom_die_id, self._coerce_optional_int(card.parameters.get("bottom_die_id")))
        try:
            return DieDimensions.from_mapping(dict(raw_mapping), default_id=default_id)
        except Exception as exc:
            raise PreprocessorCompileError(
                f"{operation_family} card operation_id={card.operation_id} has invalid {mapping_key}: {exc}"
            ) from exc

    def _resolve_press_mode_parameters(
        self,
        *,
        card: ProcessCard,
        control_parameters: Mapping[str, object],
        default_id: int | None,
        operation_family: str = "Forming",
    ) -> PressModeParameters:
        raw_mapping = self._first_mapping(
            card.parameters.get("press_mode_properties"),
            control_parameters.get("press_mode_properties"),
        )
        if raw_mapping is None:
            raise PreprocessorCompileError(
                f"{operation_family} card operation_id={card.operation_id} requires press_mode_properties"
            )
        try:
            return PressModeParameters.from_mapping(dict(raw_mapping), default_id=default_id)
        except Exception as exc:
            raise PreprocessorCompileError(
                f"{operation_family} card operation_id={card.operation_id} has invalid press_mode_properties: {exc}"
            ) from exc

    def _resolve_speed_mm_per_s(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
        parameter_values: Mapping[str, object],
        control_parameters: Mapping[str, object],
        press_mode: PressModeParameters,
    ) -> float:
        self._validate_explicit_speed_fields(
            card=card,
            parameter_values=parameter_values,
            control_parameters=control_parameters,
        )

        candidate_names: list[str] = []
        has_operation_local_speed = OPERATION_LOCAL_SPEED_FIELD in operation.db_column_names
        if has_operation_local_speed:
            candidate_names.append(OPERATION_LOCAL_SPEED_FIELD)
        if operation.speed_column_name:
            candidate_names.append(operation.speed_column_name)
        if not has_operation_local_speed:
            candidate_names.append(OPERATION_LOCAL_SPEED_FIELD)

        seen: set[str] = set()
        for name in candidate_names:
            if name in seen:
                continue
            seen.add(name)
            raw_value = self._first_present_value(
                parameter_values.get(name),
                control_parameters.get(name),
                card.parameters.get(name),
            )
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                raise PreprocessorCompileError(
                    f"Card operation_id={card.operation_id} parameter {name!r} must be numeric"
                )
            if value > 0.0:
                if value > press_mode.working_speed_mm_per_s:
                    raise PreprocessorCompileError(
                        f"Card operation_id={card.operation_id} parameter {name!r}={value:g} mm/s exceeds "
                        f"press mode working speed {press_mode.working_speed_mm_per_s:g} mm/s"
                    )
                return value
            raise PreprocessorCompileError(
                f"Card operation_id={card.operation_id} parameter {name!r} must be positive"
            )

        required_name = operation.speed_column_name or OPERATION_LOCAL_SPEED_FIELD
        raise PreprocessorCompileError(
            f"Card operation_id={card.operation_id} requires explicit positive {required_name!r} [mm/s]"
        )

    def _validate_explicit_speed_fields(
        self,
        *,
        card: ProcessCard,
        parameter_values: Mapping[str, object],
        control_parameters: Mapping[str, object],
    ) -> None:
        speed_field_names = (*OLD_FORMING_SPEED_FIELDS, OPERATION_LOCAL_SPEED_FIELD)
        for name in speed_field_names:
            raw_value = self._first_present_value(
                parameter_values.get(name),
                control_parameters.get(name),
                card.parameters.get(name),
            )
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise PreprocessorCompileError(
                    f"Card operation_id={card.operation_id} parameter {name!r} must be numeric"
                ) from exc
            if value <= 0.0:
                raise PreprocessorCompileError(
                    f"Card operation_id={card.operation_id} parameter {name!r} must be positive"
                )

    def _feed_direction_field_for_operation(self, operation: OperationTypeDefinition) -> str:
        if operation.speed_column_name == "speed_upsetting" or operation.deformation_type == "upsetting":
            return FEED_DIRECTION_UPSETTING_FIELD
        if operation.deformation_type == "full_die":
            return FEED_DIRECTION_TRANSVERSAL_COGGING_FIELD
        return FEED_DIRECTION_PROLONGATION_FIELD

    def _resolve_feed_direction_id(
        self,
        *,
        card: ProcessCard,
        operation: OperationTypeDefinition,
    ) -> int:
        field = self._feed_direction_field_for_operation(operation)
        return (
            self._coerce_optional_int(card.parameters.get(field))
            or self._coerce_optional_int(card.parameters.get(FEED_DIRECTION_LEGACY_FIELD))
            or FEED_DIRECTION_DEFAULT_ID
        )

    def _resolve_previous_feed_direction_id(
        self,
        previous: CompiledControlProgramRow,
        operation: OperationTypeDefinition,
    ) -> int | None:
        field = self._feed_direction_field_for_operation(operation)
        return (
            self._coerce_optional_int(previous.metrics.get(field))
            or self._coerce_optional_int(previous.metrics.get(FEED_DIRECTION_LEGACY_FIELD))
        )

    def _store_feed_direction_metrics(
        self,
        metrics: dict[str, object],
        operation: OperationTypeDefinition,
        feed_direction_id: int,
    ) -> None:
        field = self._feed_direction_field_for_operation(operation)
        metrics[field] = feed_direction_id
        metrics[FEED_DIRECTION_LEGACY_FIELD] = feed_direction_id

    def _require_previous_row(
        self,
        previous_row: CompiledControlProgramRow | None,
        card: ProcessCard,
        operation_family: str,
    ) -> CompiledControlProgramRow:
        if previous_row is None:
            raise PreprocessorCompileError(
                f"{operation_family.capitalize()} card operation_id={card.operation_id} requires a previous compiled row"
            )
        return previous_row

    def _require_geometry(
        self,
        geometry: GeneratedGeometry | None,
        card: ProcessCard,
        operation_family: str,
    ) -> GeneratedGeometry:
        if geometry is None:
            raise PreprocessorCompileError(
                f"{operation_family.capitalize()} card operation_id={card.operation_id} requires carried billet geometry"
            )
        return geometry

    def _get_float_parameter(self, card: ProcessCard, name: str) -> float:
        value = card.parameters.get(name)
        if value is None:
            raise PreprocessorCompileError(
                f"Card operation_id={card.operation_id} requires numeric parameter {name!r}"
            )
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise PreprocessorCompileError(
                f"Card operation_id={card.operation_id} parameter {name!r} must be numeric"
            ) from exc

    def _optional_int_parameter(self, card: ProcessCard, name: str) -> int | None:
        value = card.parameters.get(name)
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise PreprocessorCompileError(
                f"Card operation_id={card.operation_id} parameter {name!r} must be an integer"
            ) from exc

    def _first_float_parameter(
        self,
        card: ProcessCard,
        *names: str,
        default: float | None = None,
    ) -> float:
        for name in names:
            value = card.parameters.get(name)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise PreprocessorCompileError(
                    f"Card operation_id={card.operation_id} parameter {name!r} must be numeric"
                ) from exc
        if default is not None:
            return default
        raise PreprocessorCompileError(
            f"Card operation_id={card.operation_id} requires one of numeric parameters {names!r}"
        )

    def _first_optional_float(self, card: ProcessCard, *names: str) -> float | None:
        for name in names:
            value = card.parameters.get(name)
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise PreprocessorCompileError(
                    f"Card operation_id={card.operation_id} parameter {name!r} must be numeric"
                ) from exc
        return None

    def _last_program_temperature(self, value: object) -> float | None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return None
        last_temperature: float | None = None
        for raw_row in value:
            if not isinstance(raw_row, Mapping):
                continue
            if str(raw_row.get("type") or "hold") != "hold":
                continue
            raw_temperature = raw_row.get("temperature_c")
            if raw_temperature in (None, ""):
                continue
            try:
                last_temperature = float(raw_temperature)
            except (TypeError, ValueError) as exc:
                raise PreprocessorCompileError(
                    f"temperature_program hold row temperature_c={raw_temperature!r} must be numeric"
                ) from exc
        return last_temperature

    @staticmethod
    def _first_present_value(*values: object) -> object | None:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            return value
        return None

    def _resolve_prolongation_angle(self, card: ProcessCard) -> float:
        template_id = card.operation_template_id or ""
        if template_id in AXIAL_PROLONGATION_TEMPLATE_IDS:
            return self._first_optional_float(card, "rotation", "angle") or 0.0
        if template_id in {RADIAL_ROTATION_HEIGHT_FEED, RADIAL_HEIGHT_BITES}:
            return self._first_optional_float(card, "rotation_manipulator", "angle") or 0.0
        if template_id == RADIAL_PRESS_AXIS_FEED or template_id in FULL_DIE_TEMPLATE_IDS:
            return self._first_optional_float(card, "rotation", "angle") or 0.0
        return 0.0

    def _parse_skip_bites(self, value: object) -> tuple[int, ...]:
        if value is None or value == "":
            return ()
        if isinstance(value, int):
            return (value,)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            parsed: list[int] = []
            for item in value:
                try:
                    parsed.append(int(item))
                except (TypeError, ValueError) as exc:
                    raise PreprocessorCompileError(f"skip_bites contains non-integer value {item!r}") from exc
            return tuple(parsed)
        if isinstance(value, str):
            parsed = []
            for item in value.split(","):
                item = item.strip()
                if not item:
                    continue
                try:
                    parsed.append(int(item))
                except ValueError as exc:
                    raise PreprocessorCompileError(f"skip_bites contains non-integer value {item!r}") from exc
            return tuple(parsed)
        raise PreprocessorCompileError(f"skip_bites has unsupported value {value!r}")

    def _coerce_optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _first_optional_int(self, *values: object) -> int | None:
        for value in values:
            coerced = self._coerce_optional_int(value)
            if coerced is not None:
                return coerced
        return None

    def _first_mapping(self, *values: object) -> Mapping[str, object] | None:
        for value in values:
            if isinstance(value, Mapping):
                return value
        return None

    def _infer_step_control(self, operation: OperationTypeDefinition) -> str | None:
        if operation.operation_template_id in CUTTING_TEMPLATE_IDS:
            return "StepsNum"
        if "num_of_bites" in operation.db_column_names:
            return "StepsNum"
        return "Feed"

    def _surface_area_mm2(self, geometry: GeneratedGeometry) -> float:
        perimeter = self._outline_perimeter_mm(geometry.cross_section_outline)
        return 2.0 * geometry.cross_section_area_mm2 + perimeter * geometry.length_mm

    def _safe_surface_pair(self, context: str, producer: Callable[[], LegacySurfacePair]) -> LegacySurfacePair:
        """Run legacy surface generation and fail loudly on missing algorithms/data."""

        try:
            return producer()
        except SurfaceMeshError as exc:
            raise PreprocessorCompileError(
                f"Legacy STL mesh generation failed for {context}: {exc}"
            ) from exc

    def _outline_perimeter_mm(self, outline: Sequence[tuple[float, float]]) -> float:
        if len(outline) < 2:
            return 0.0
        perimeter = 0.0
        for index, point in enumerate(outline):
            next_point = outline[(index + 1) % len(outline)]
            perimeter += math.dist(point, next_point)
        return perimeter

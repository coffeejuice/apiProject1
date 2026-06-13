"""Typed cogging/prolongation calculation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.preprocessor.geometry import GeneratedGeometry
from app.services.preprocessor.upsetting import DieDimensions, PressModeParameters


class CoggingMathError(ValueError):
    """Raised when cogging/prolongation inputs are inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class CoggingCalculationInput:
    """Normalized scalar inputs for one cogging/prolongation operation."""

    template_id: str
    initial_geometry: GeneratedGeometry
    press_mode: PressModeParameters
    top_die: DieDimensions
    bottom_die: DieDimensions
    speed_mm_per_s: float
    previous_total_time_seconds: float
    time_between_operation_seconds: float | None
    angle_deg: float = 0.0
    final_height_mm: float | None = None
    final_diameter_mm: float | None = None
    radial_feed_mm: float | None = None
    feed_mm: float | None = None
    feed_first_mm: float | None = None
    feed_middle_mm: float | None = None
    feed_last_mm: float | None = None
    num_of_bites_input: int | None = None
    skip_bites: tuple[int, ...] = ()
    rotation_per_bite_deg: float = 0.0
    current_feed_direction_id: int | None = None
    previous_feed_direction_id: int | None = None
    is_same_operation_type_as_previous: bool = False
    mesh_elements: int | None = None
    extra_rotations: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeedSchedule:
    """Feed values used to build the bite table."""

    feed_first_mm: float
    feed_middle_mm: float
    feed_last_mm: float
    num_of_bites_input: int | None
    skip_bites: tuple[int, ...] = ()
    rotations_count_per_feed_list: tuple[int, int, int] = (0, 0, 0)
    rotation_per_bite_deg: float = 0.0


@dataclass(frozen=True, slots=True)
class CoggingStrains:
    """Principal logarithmic strains for the current operation."""

    strain_length: float
    strain_height: float
    strain_width: float


@dataclass(frozen=True, slots=True)
class CoggingVariantResult:
    """Per-variant calculation output before common timing and payload assembly."""

    final_geometry: GeneratedGeometry
    penetration_mm: float
    feed_schedule: FeedSchedule
    initial_length_of_contact_mm: float
    final_length_of_contact_mm: float
    final_width_of_contact_mm: float
    strains: CoggingStrains
    operation_specific_parameters: dict[str, Any] = field(default_factory=dict)
    compiler_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CoggingComputationResult:
    """All cogging/prolongation-derived outputs for one control-program row."""

    final_geometry: GeneratedGeometry
    metrics: dict[str, Any]
    operation_specific_parameters: dict[str, Any] = field(default_factory=dict)
    total_time_seconds: float = 0.0
    time_before_operation_seconds: float | None = None
    simulation_expected_duration_days: float | None = None
    compiler_notes: tuple[str, ...] = ()

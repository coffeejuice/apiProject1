"""Compatibility entrypoint for cogging/prolongation calculations.

The engineer-readable implementation lives under
``app.services.preprocessor.cogging``. This module keeps the historical
``calculate_prolongation`` import stable for existing compiler/API code.
"""

from __future__ import annotations

from .cogging import (
    CoggingCalculationInput,
    CoggingComputationResult,
    CoggingMathError,
    calculate_cogging,
)
from .geometry import GeneratedGeometry
from .upsetting import DieDimensions, PressModeParameters


ProlongationMathError = CoggingMathError
ProlongationComputationResult = CoggingComputationResult


def calculate_prolongation(
    *,
    template_id: str,
    initial_geometry: GeneratedGeometry,
    press_mode: PressModeParameters,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    speed_mm_per_s: float,
    previous_total_time_seconds: float,
    time_between_operation_seconds: float | None,
    angle_deg: float = 0.0,
    final_height_mm: float | None = None,
    final_diameter_mm: float | None = None,
    radial_feed_mm: float | None = None,
    feed_mm: float | None = None,
    feed_first_mm: float | None = None,
    feed_middle_mm: float | None = None,
    feed_last_mm: float | None = None,
    num_of_bites_input: int | None = None,
    skip_bites: tuple[int, ...] = (),
    rotation_per_bite_deg: float = 0.0,
    current_feed_direction_id: int | None = None,
    previous_feed_direction_id: int | None = None,
    is_same_operation_type_as_previous: bool = False,
    mesh_elements: int | None = None,
    extra_rotations: dict[str, float] | None = None,
) -> ProlongationComputationResult:
    """Compute cogging/prolongation outputs through the new typed adapter."""

    return calculate_cogging(
        CoggingCalculationInput(
            template_id=template_id,
            initial_geometry=initial_geometry,
            press_mode=press_mode,
            top_die=top_die,
            bottom_die=bottom_die,
            speed_mm_per_s=speed_mm_per_s,
            previous_total_time_seconds=previous_total_time_seconds,
            time_between_operation_seconds=time_between_operation_seconds,
            angle_deg=angle_deg,
            final_height_mm=final_height_mm,
            final_diameter_mm=final_diameter_mm,
            radial_feed_mm=radial_feed_mm,
            feed_mm=feed_mm,
            feed_first_mm=feed_first_mm,
            feed_middle_mm=feed_middle_mm,
            feed_last_mm=feed_last_mm,
            num_of_bites_input=num_of_bites_input,
            skip_bites=skip_bites,
            rotation_per_bite_deg=rotation_per_bite_deg,
            current_feed_direction_id=current_feed_direction_id,
            previous_feed_direction_id=previous_feed_direction_id,
            is_same_operation_type_as_previous=is_same_operation_type_as_previous,
            mesh_elements=mesh_elements,
            extra_rotations=extra_rotations or {},
        )
    )


__all__ = [
    "ProlongationComputationResult",
    "ProlongationMathError",
    "calculate_prolongation",
]

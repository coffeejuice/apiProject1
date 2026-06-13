"""Transversal/full-die cogging by rotation and final height."""

from __future__ import annotations

from ..contours_2d.full_die import build_full_die_height_reduction_contour
from ..models import CoggingCalculationInput, CoggingVariantResult, FeedSchedule
from ._height_reduction import calculate_height_reduction_variant


def calculate(input_data: CoggingCalculationInput) -> CoggingVariantResult:
    """Calculate one-bite transversal height reduction."""

    return calculate_height_reduction_variant(
        input_data=input_data,
        feed_schedule=FeedSchedule(
            feed_first_mm=input_data.initial_geometry.length_mm,
            feed_middle_mm=0.0,
            feed_last_mm=0.0,
            num_of_bites_input=1,
        ),
        contour_builder=build_full_die_height_reduction_contour,
        operation_specific_parameters={
            "full_die_adapter": True,
            "full_die_rotation": input_data.angle_deg,
        },
        full_die_single_bite=True,
    )

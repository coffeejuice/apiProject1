"""Radial cogging by final height and bite count."""

from __future__ import annotations

from ..contours_2d.radial import build_radial_height_reduction_contour
from ..models import CoggingCalculationInput, CoggingVariantResult, FeedSchedule
from ..shared_formulas import require_positive_int
from ._height_reduction import calculate_height_reduction_variant


def calculate(input_data: CoggingCalculationInput) -> CoggingVariantResult:
    """Calculate radial cogging from target height plus requested bite count."""

    num_of_bites = require_positive_int(input_data.num_of_bites_input, "num_of_bites")
    feed_first_mm = input_data.initial_geometry.length_mm / num_of_bites

    return calculate_height_reduction_variant(
        input_data=input_data,
        feed_schedule=FeedSchedule(
            feed_first_mm=feed_first_mm,
            feed_middle_mm=0.0,
            feed_last_mm=0.0,
            num_of_bites_input=num_of_bites,
        ),
        contour_builder=build_radial_height_reduction_contour,
        operation_specific_parameters={
            "radial_initial_rotations": [("y", 90.0)],
            "radial_accumulated_billet_rotation": input_data.angle_deg,
            "radial_rotations": [("y", 90.0), ("x", input_data.angle_deg)],
        },
    )

"""Transverse/full-die all-in-one cogging."""

from __future__ import annotations

from ..contours_2d.full_die import build_full_die_height_reduction_contour
from ..models import CoggingCalculationInput, CoggingVariantResult, FeedSchedule
from ..shared_formulas import default_axial_feed_mm, positive_or_default, require_positive_int
from ._height_reduction import calculate_height_reduction_variant


def calculate(input_data: CoggingCalculationInput) -> CoggingVariantResult:
    """Calculate transverse/full-die cogging from height plus feed or bite count."""

    if input_data.num_of_bites_input is not None and int(input_data.num_of_bites_input) > 0:
        num_of_bites = require_positive_int(input_data.num_of_bites_input, "num_of_bites")
        feed_schedule = FeedSchedule(
            feed_first_mm=input_data.initial_geometry.length_mm / num_of_bites,
            feed_middle_mm=0.0,
            feed_last_mm=0.0,
            num_of_bites_input=num_of_bites,
        )
    else:
        feed_first_mm = positive_or_default(
            input_data.feed_first_mm,
            input_data.feed_mm,
            default_axial_feed_mm(input_data),
        )
        feed_middle_mm = positive_or_default(input_data.feed_middle_mm, feed_first_mm)
        feed_last_mm = positive_or_default(input_data.feed_last_mm, feed_middle_mm)
        feed_schedule = FeedSchedule(
            feed_first_mm=feed_first_mm,
            feed_middle_mm=feed_middle_mm,
            feed_last_mm=feed_last_mm,
            num_of_bites_input=None,
        )

    return calculate_height_reduction_variant(
        input_data=input_data,
        feed_schedule=feed_schedule,
        contour_builder=build_full_die_height_reduction_contour,
        operation_specific_parameters={
            "full_die_adapter": True,
            "full_die_rotation": input_data.angle_deg,
        },
        full_die_single_bite=feed_schedule.num_of_bites_input == 1,
    )

"""Axial cogging by final height and feed lengths."""

from __future__ import annotations

from ..contours_2d.axial import build_axial_height_reduction_contour
from ..models import CoggingCalculationInput, CoggingVariantResult, FeedSchedule
from ..shared_formulas import default_axial_feed_mm, positive_or_default
from ._height_reduction import calculate_height_reduction_variant


def calculate(input_data: CoggingCalculationInput) -> CoggingVariantResult:
    """Calculate axial cogging from target height plus first/middle/last feeds."""

    feed_first_mm = positive_or_default(
        input_data.feed_first_mm,
        input_data.feed_mm,
        default_axial_feed_mm(input_data),
    )
    feed_middle_mm = positive_or_default(input_data.feed_middle_mm, feed_first_mm)
    feed_last_mm = positive_or_default(input_data.feed_last_mm, feed_middle_mm)

    return calculate_height_reduction_variant(
        input_data=input_data,
        feed_schedule=FeedSchedule(
            feed_first_mm=feed_first_mm,
            feed_middle_mm=feed_middle_mm,
            feed_last_mm=feed_last_mm,
            num_of_bites_input=None,
        ),
        contour_builder=build_axial_height_reduction_contour,
    )

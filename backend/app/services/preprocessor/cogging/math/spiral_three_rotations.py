"""Spiral rounding with three-rotation middle-feed mode."""

from __future__ import annotations

from ..models import CoggingCalculationInput, CoggingVariantResult
from ._spiral import calculate_spiral_variant


def calculate(input_data: CoggingCalculationInput) -> CoggingVariantResult:
    """Calculate three-rotation spiral rounding."""

    return calculate_spiral_variant(
        input_data=input_data,
        rotations_count_per_feed_list=(5, 2, 5),
    )

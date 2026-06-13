"""Narrow adapter from semantic operation templates to cogging math variants."""

from __future__ import annotations

from collections.abc import Callable

from app.services.preprocessor.operation_keys import (
    PROLONGATION_HEIGHT_BITES,
    PROLONGATION_ROTATION_HEIGHT,
    PROLONGATION_SKIP_BITES,
    PROLONGATION_TEMPLATE_IDS,
    RADIAL_HEIGHT_BITES,
    RADIAL_PRESS_AXIS_FEED,
    RADIAL_ROTATION_HEIGHT_FEED,
    ROUNDING_SPIRAL_ONE_ROTATION,
    ROUNDING_SPIRAL_THREE_ROTATIONS,
    TRANSVERSAL_ROTATION_HEIGHT,
    TRANSVERSE_ALL_IN_ONE,
)

from .math import (
    axial_height_bites,
    axial_height_feed,
    axial_skip_bites,
    radial_height_bites,
    radial_height_feed,
    radial_press_axis_feed,
    spiral_one_rotation,
    spiral_three_rotations,
    transversal_rotation_height,
    transverse_all_in_one,
)
from .models import CoggingCalculationInput, CoggingComputationResult, CoggingMathError, CoggingVariantResult
from .shared_formulas import assemble_cogging_result, validate_press_and_geometry


VariantCalculator = Callable[[CoggingCalculationInput], CoggingVariantResult]


_VARIANT_CALCULATORS: dict[str, VariantCalculator] = {
    PROLONGATION_ROTATION_HEIGHT: axial_height_feed.calculate,
    PROLONGATION_HEIGHT_BITES: axial_height_bites.calculate,
    PROLONGATION_SKIP_BITES: axial_skip_bites.calculate,
    ROUNDING_SPIRAL_ONE_ROTATION: spiral_one_rotation.calculate,
    ROUNDING_SPIRAL_THREE_ROTATIONS: spiral_three_rotations.calculate,
    RADIAL_ROTATION_HEIGHT_FEED: radial_height_feed.calculate,
    RADIAL_HEIGHT_BITES: radial_height_bites.calculate,
    RADIAL_PRESS_AXIS_FEED: radial_press_axis_feed.calculate,
    TRANSVERSE_ALL_IN_ONE: transverse_all_in_one.calculate,
    TRANSVERSAL_ROTATION_HEIGHT: transversal_rotation_height.calculate,
}


def calculate_cogging(input_data: CoggingCalculationInput) -> CoggingComputationResult:
    """Calculate one cogging/prolongation operation through its typed variant."""

    if input_data.template_id not in PROLONGATION_TEMPLATE_IDS:
        raise CoggingMathError(f"Unsupported prolongation template_id={input_data.template_id}")
    validate_press_and_geometry(input_data)

    variant_calculator = _VARIANT_CALCULATORS.get(input_data.template_id)
    if variant_calculator is None:
        raise CoggingMathError(f"Unsupported prolongation template_id={input_data.template_id}")

    variant = variant_calculator(input_data)
    return assemble_cogging_result(input_data=input_data, variant=variant)

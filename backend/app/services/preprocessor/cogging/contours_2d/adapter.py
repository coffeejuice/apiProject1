"""Narrow 2D contour dispatcher for cogging/prolongation."""

from __future__ import annotations

from collections.abc import Callable

from app.services.preprocessor.operation_keys import (
    AXIAL_PROLONGATION_TEMPLATE_IDS,
    FULL_DIE_TEMPLATE_IDS,
    RADIAL_PROLONGATION_TEMPLATE_IDS,
    SPIRAL_PROLONGATION_TEMPLATE_IDS,
)
from app.services.preprocessor.prolongation_geometry import ProlongationGeometryResult

from .axial import build_axial_height_reduction_contour
from .full_die import build_full_die_height_reduction_contour
from .models import HeightReductionContourInput, SpiralRoundContourInput
from .radial import build_radial_height_reduction_contour
from .spiral import build_spiral_rounding_contour


HeightContourBuilder = Callable[[HeightReductionContourInput], ProlongationGeometryResult]


def height_reduction_contour_builder(template_id: str) -> HeightContourBuilder:
    """Return the contour builder for one non-spiral cogging template."""

    if template_id in AXIAL_PROLONGATION_TEMPLATE_IDS:
        return build_axial_height_reduction_contour
    if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS:
        return build_radial_height_reduction_contour
    if template_id in FULL_DIE_TEMPLATE_IDS:
        return build_full_die_height_reduction_contour
    raise ValueError(f"No height-reduction contour builder for template_id={template_id}")


def build_spiral_contour(input_data: SpiralRoundContourInput) -> ProlongationGeometryResult:
    """Build the 2D contour for a spiral rounding operation."""

    return build_spiral_rounding_contour(input_data)

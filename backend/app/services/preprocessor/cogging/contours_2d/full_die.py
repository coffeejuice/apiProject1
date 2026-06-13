"""2D contour generation for transverse/full-die cogging."""

from __future__ import annotations

from app.services.preprocessor.prolongation_geometry import ProlongationGeometryResult

from .models import HeightReductionContourInput
from .shared import build_height_reduction_contour


def build_full_die_height_reduction_contour(
    input_data: HeightReductionContourInput,
) -> ProlongationGeometryResult:
    """Build the final transverse/full-die cross-section contour."""

    return build_height_reduction_contour(input_data)

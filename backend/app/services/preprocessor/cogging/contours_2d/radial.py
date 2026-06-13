"""2D contour generation for radial cogging/prolongation."""

from __future__ import annotations

from app.services.preprocessor.prolongation_geometry import ProlongationGeometryResult

from .models import HeightReductionContourInput
from .shared import build_height_reduction_contour


def build_radial_height_reduction_contour(
    input_data: HeightReductionContourInput,
) -> ProlongationGeometryResult:
    """Build the final radial cogging cross-section contour."""

    return build_height_reduction_contour(input_data)

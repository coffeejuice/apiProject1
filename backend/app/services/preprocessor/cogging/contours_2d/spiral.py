"""2D contour generation for spiral rounding."""

from __future__ import annotations

from app.services.preprocessor.prolongation_geometry import ProlongationGeometryResult

from .models import SpiralRoundContourInput
from .shared import build_spiral_round_contour


def build_spiral_rounding_contour(input_data: SpiralRoundContourInput) -> ProlongationGeometryResult:
    """Build the final spiral-rounding cross-section contour."""

    return build_spiral_round_contour(input_data)

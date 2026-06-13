"""2D contour layer for cogging/prolongation."""

from .adapter import build_spiral_contour, height_reduction_contour_builder
from .models import HeightReductionContourInput, SpiralRoundContourInput

__all__ = [
    "HeightReductionContourInput",
    "SpiralRoundContourInput",
    "build_spiral_contour",
    "height_reduction_contour_builder",
]

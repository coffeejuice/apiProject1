"""Shared adapters to the migrated Shapely 2D contour implementation."""

from __future__ import annotations

from app.services.preprocessor.prolongation_geometry import (
    ProlongationGeometryResult,
    apply_die_trimming_geometry,
    build_spiral_round_geometry,
)

from .models import HeightReductionContourInput, SpiralRoundContourInput


def build_height_reduction_contour(input_data: HeightReductionContourInput) -> ProlongationGeometryResult:
    """Run the die-trimming contour path for a height-reduction variant."""

    return apply_die_trimming_geometry(
        initial_geometry=input_data.initial_geometry,
        final_height_mm=input_data.final_height_mm,
        penetration_mm=input_data.penetration_mm,
        top_die=input_data.top_die,
        bottom_die=input_data.bottom_die,
        angle_deg=input_data.angle_deg,
        final_length_of_contact_mm=input_data.final_length_of_contact_mm,
        strain_height=input_data.strain_height,
    )


def build_spiral_round_contour(input_data: SpiralRoundContourInput) -> ProlongationGeometryResult:
    """Run the round-contour path for a spiral rounding variant."""

    return build_spiral_round_geometry(
        initial_geometry=input_data.initial_geometry,
        final_diameter_mm=input_data.final_diameter_mm,
    )

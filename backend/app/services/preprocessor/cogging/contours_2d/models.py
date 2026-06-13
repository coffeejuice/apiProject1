"""Typed 2D contour inputs for cogging/prolongation."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.preprocessor.geometry import GeneratedGeometry
from app.services.preprocessor.upsetting import DieDimensions


@dataclass(frozen=True, slots=True)
class HeightReductionContourInput:
    """Inputs for die-trimmed height-reduction cross-section generation."""

    initial_geometry: GeneratedGeometry
    final_height_mm: float
    penetration_mm: float
    top_die: DieDimensions
    bottom_die: DieDimensions
    angle_deg: float
    final_length_of_contact_mm: float
    strain_height: float


@dataclass(frozen=True, slots=True)
class SpiralRoundContourInput:
    """Inputs for spiral-rounding final cross-section generation."""

    initial_geometry: GeneratedGeometry
    final_diameter_mm: float

"""3D surface generation for spiral rounding."""

from __future__ import annotations

from app.services.preprocessor.legacy_surface_mesh import LegacySurfaceMeshBuilder, LegacySurfacePair

from .models import CoggingSurfaceInput
from .shared import build_legacy_prolongation_surface


def build_spiral_surface(
    input_data: CoggingSurfaceInput,
    *,
    builder: LegacySurfaceMeshBuilder | None = None,
) -> LegacySurfacePair:
    """Build spiral-rounding initial/final surface meshes."""

    return build_legacy_prolongation_surface(input_data, builder=builder)

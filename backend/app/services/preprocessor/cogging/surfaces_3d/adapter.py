"""Narrow 3D surface dispatcher for cogging/prolongation."""

from __future__ import annotations

from app.services.preprocessor.legacy_surface_mesh import LegacySurfaceMeshBuilder, LegacySurfacePair
from app.services.preprocessor.operation_keys import (
    AXIAL_PROLONGATION_TEMPLATE_IDS,
    FULL_DIE_TEMPLATE_IDS,
    RADIAL_PROLONGATION_TEMPLATE_IDS,
    SPIRAL_PROLONGATION_TEMPLATE_IDS,
)

from .axial import build_axial_surface
from .full_die import build_full_die_surface
from .models import CoggingSurfaceInput
from .radial import build_radial_surface
from .spiral import build_spiral_surface


def build_cogging_surface_pair(
    input_data: CoggingSurfaceInput,
    *,
    builder: LegacySurfaceMeshBuilder | None = None,
) -> LegacySurfacePair:
    """Build 3D surfaces for one cogging/prolongation template."""

    template_id = input_data.template_id
    if template_id in AXIAL_PROLONGATION_TEMPLATE_IDS:
        return build_axial_surface(input_data, builder=builder)
    if template_id in SPIRAL_PROLONGATION_TEMPLATE_IDS:
        return build_spiral_surface(input_data, builder=builder)
    if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS:
        return build_radial_surface(input_data, builder=builder)
    if template_id in FULL_DIE_TEMPLATE_IDS:
        return build_full_die_surface(input_data, builder=builder)
    return build_axial_surface(input_data, builder=builder)

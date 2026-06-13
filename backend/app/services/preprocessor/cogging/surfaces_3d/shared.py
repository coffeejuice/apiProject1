"""Shared adapter to the migrated legacy surface-mesh implementation."""

from __future__ import annotations

from app.services.preprocessor.legacy_surface_mesh import LegacySurfaceMeshBuilder, LegacySurfacePair

from .models import CoggingSurfaceInput


def build_legacy_prolongation_surface(
    input_data: CoggingSurfaceInput,
    *,
    builder: LegacySurfaceMeshBuilder | None = None,
) -> LegacySurfacePair:
    """Build 3D surfaces with the current legacy-compatible mesh algorithm."""

    surface_builder = builder or LegacySurfaceMeshBuilder()
    return surface_builder.prolongation(
        previous_final=input_data.previous_final,
        initial_geometry=input_data.initial_geometry,
        final_geometry=input_data.final_geometry,
        metrics=input_data.metrics,
        operation_specific_parameters=input_data.operation_specific_parameters,
        template_id=input_data.template_id,
    )

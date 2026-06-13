"""Typed 3D surface inputs for cogging/prolongation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.services.preprocessor.geometry import GeneratedGeometry
from app.services.preprocessor.surface_mesh import SurfaceMesh


@dataclass(frozen=True, slots=True)
class CoggingSurfaceInput:
    """Inputs for generating initial/final 3D surface meshes for one cogging row."""

    previous_final: SurfaceMesh | None
    initial_geometry: GeneratedGeometry
    final_geometry: GeneratedGeometry
    metrics: Mapping[str, Any]
    operation_specific_parameters: Mapping[str, Any]
    template_id: str | None

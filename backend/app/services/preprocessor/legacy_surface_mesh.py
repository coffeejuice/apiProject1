"""Legacy Trimesh/STL surface generation ported from the old preprocessor.

This module intentionally keeps the old mesh-state model: every deformation row
starts from the previous row's final STL mesh, then applies operation-specific
transforms. It is separate from the numeric deformation math so we can later
optimize or replace the algorithms without changing compiler dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import Polygon

from app.services.preprocessor.geometry import GeneratedGeometry
from app.services.preprocessor.operation_keys import (
    CUTTING_TEMPLATE_IDS,
    FULL_DIE_TEMPLATE_IDS,
    RADIAL_PROLONGATION_TEMPLATE_IDS,
    SPIRAL_PROLONGATION_TEMPLATE_IDS,
    UPSETTING_TEMPLATE_IDS,
)
from app.services.preprocessor.surface_mesh import SurfaceMesh, SurfaceMeshError


RotationSpec = Sequence[tuple[str, float]]


@dataclass(frozen=True, slots=True)
class LegacySurfacePair:
    """Initial/final surface meshes plus non-fatal porting notes."""

    initial: SurfaceMesh | None
    final: SurfaceMesh | None
    notes: tuple[str, ...] = ()


class LegacySurfaceMeshBuilder:
    """Generate 3D surfaces using the old preprocessor's Trimesh approach."""

    def billet(self, geometry: GeneratedGeometry) -> LegacySurfacePair:
        mesh = SurfaceMesh.from_trimesh(
            polygon_to_3d_trimesh_object(_geometry_polygon(geometry), geometry.length_mm),
            cross_section_point_count=len(geometry.cross_section_outline),
        )
        return LegacySurfacePair(initial=mesh, final=mesh)

    def static(self, previous_final: SurfaceMesh | None) -> LegacySurfacePair:
        """Heating/Furnace rows do not deform the billet surface."""

        if previous_final is None:
            raise SurfaceMeshError("No previous final mesh for static surface carry.")
        return LegacySurfacePair(initial=previous_final, final=previous_final)

    def upsetting(
        self,
        *,
        previous_final: SurfaceMesh | None,
        initial_geometry: GeneratedGeometry,
        final_geometry: GeneratedGeometry,
        metrics: Mapping[str, Any],
        operation_specific_parameters: Mapping[str, Any],
        template_id: str | None,
    ) -> LegacySurfacePair:
        if previous_final is None:
            raise SurfaceMeshError("No previous final mesh for upsetting surface.")

        initial_trimesh = _surface_to_trimesh(previous_final)
        initial_rotations = _rotation_list(operation_specific_parameters.get("radial_rotations"))
        if initial_rotations:
            initial_trimesh = rotate_trimesh_object(initial_trimesh, initial_rotations)

        if template_id == "upsetting.tail_chamfering":
            scaled = _legacy_final_3d_stl_like(
                initial_trimesh,
                initial_geometry=initial_geometry,
                final_geometry=final_geometry,
            )
        else:
            strain_x = _float(metrics.get("strain_height"), default=0.0)
            strain_y = _float(metrics.get("strain_width"), default=0.0)
            strain_z = _float(metrics.get("strain_length"), default=0.0)
            scaled = _scale_trimesh(initial_trimesh, math.exp(strain_x), math.exp(strain_y), math.exp(strain_z))

        # Old _final_basis for upsetting reverses only the final Y rotation.
        final_trimesh = rotate_trimesh_object(scaled, (("y", -90.0),))
        return LegacySurfacePair(
            initial=SurfaceMesh.from_trimesh(initial_trimesh),
            final=SurfaceMesh.from_trimesh(final_trimesh),
        )

    def prolongation(
        self,
        *,
        previous_final: SurfaceMesh | None,
        initial_geometry: GeneratedGeometry,
        final_geometry: GeneratedGeometry,
        metrics: Mapping[str, Any],
        operation_specific_parameters: Mapping[str, Any],
        template_id: str | None,
    ) -> LegacySurfacePair:
        if previous_final is None:
            raise SurfaceMeshError("No previous final mesh for deformation surface.")

        initial_trimesh = _surface_to_trimesh(previous_final)
        direct_rotations = _prolongation_initial_rotations(
            template_id=template_id,
            metrics=metrics,
            operation_specific_parameters=operation_specific_parameters,
        )
        if direct_rotations:
            initial_trimesh = rotate_trimesh_object(initial_trimesh, direct_rotations)

        if template_id in SPIRAL_PROLONGATION_TEMPLATE_IDS or template_id in FULL_DIE_TEMPLATE_IDS:
            final_trimesh = _legacy_final_3d_stl_like(
                initial_trimesh,
                initial_geometry=initial_geometry,
                final_geometry=final_geometry,
            )
        else:
            final_trimesh = _legacy_final_polygon_and_trimesh_like(
                initial_trimesh,
                initial_geometry=initial_geometry,
                final_geometry=final_geometry,
            )

        if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS and direct_rotations:
            final_trimesh = rotate_trimesh_object(
                final_trimesh,
                tuple((axis, -angle) for axis, angle in reversed(direct_rotations)),
            )

        return LegacySurfacePair(
            initial=SurfaceMesh.from_trimesh(initial_trimesh),
            final=SurfaceMesh.from_trimesh(final_trimesh),
        )

    def cutting(
        self,
        *,
        previous_final: SurfaceMesh | None,
        final_geometry: GeneratedGeometry,
        template_id: str | None,
    ) -> LegacySurfacePair:
        initial = previous_final
        if template_id not in CUTTING_TEMPLATE_IDS:
            return LegacySurfacePair(initial, initial)
        final = SurfaceMesh.from_trimesh(
            polygon_to_3d_trimesh_object(_geometry_polygon(final_geometry), final_geometry.length_mm),
            cross_section_point_count=len(final_geometry.cross_section_outline),
        )
        return LegacySurfacePair(initial=initial, final=final)


def polygon_to_3d_trimesh_object(polygon: Polygon, length: float) -> Any:
    """Port of old ``polygon_to_3d_trimesh_object``."""

    trimesh = _trimesh_module()
    vertices, faces = trimesh.creation.triangulate_polygon(polygon=polygon, force_vertices=True)
    mesh_obj = trimesh.creation.extrude_triangulation(vertices=vertices, faces=faces, height=length)
    mesh_obj.apply_translation([0.0, 0.0, -0.5 * length])
    return rotate_trimesh_object(mesh_obj, (("x", 90.0), ("z", 90.0)))


def rotate_trimesh_object(trimesh_obj: Any, rotations: RotationSpec) -> Any:
    """Port of old ``rotate_trimesh_object``."""

    _trimesh_module()
    transformations = _transformations_module()
    axes = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
    mesh = trimesh_obj.copy()
    for axis_name, angle in rotations:
        if float(angle) == 0.0:
            continue
        matrix = transformations.rotation_matrix(
            angle=math.radians(float(angle)),
            direction=axes[str(axis_name)],
            point=[0, 0, 0],
        )
        mesh.apply_transform(matrix)
    return mesh


def _legacy_final_3d_stl_like(
    initial_trimesh: Any,
    *,
    initial_geometry: GeneratedGeometry,
    final_geometry: GeneratedGeometry,
) -> Any:
    """Port the old ``_final_3d_stl`` behavior used by several old operations.

    The old implementation calculated die boolean cuts but saved the transformed
    scaled initial mesh, not the boolean result. This method intentionally keeps
    that behavior for now.
    """

    if initial_geometry.height_mm <= 0.0:
        return initial_trimesh.copy()
    z_scale = final_geometry.height_mm / initial_geometry.height_mm
    return _scale_trimesh(initial_trimesh, 1.0, 1.0, z_scale)


def _legacy_final_polygon_and_trimesh_like(
    initial_trimesh: Any,
    *,
    initial_geometry: GeneratedGeometry,
    final_geometry: GeneratedGeometry,
) -> Any:
    """Port the old ``_final_polygon_and_trimesh_obj`` mesh branch.

    The old function scaled the carried mesh vertically, subtracted top/bottom
    die boxes, widened the mesh, and extended it along the billet axis. The
    current compiler already calculated the target geometry, so this method uses
    the target dimensions to reproduce that mesh-state update.
    """

    if initial_geometry.height_mm <= 0.0:
        raise SurfaceMeshError("Initial height is not positive; cannot generate legacy prolongation STL mesh.")

    mesh = _scale_trimesh(initial_trimesh, 1.0, 1.0, final_geometry.height_mm / initial_geometry.height_mm)
    mesh = _trim_with_top_bottom_boxes(mesh, final_geometry.height_mm)
    mesh = _extend_to_dimension(mesh, final_geometry.width_mm, axis_name="y")
    mesh = _extend_to_dimension(mesh, final_geometry.length_mm, axis_name="x")
    return mesh


def _trim_with_top_bottom_boxes(mesh: Any, final_height_mm: float) -> Any:
    _trimesh_module()
    from trimesh import boolean, creation

    bounds = mesh.bounds.copy()
    top_bounds = bounds.copy()
    bottom_bounds = bounds.copy()
    top_bounds[:, :2] *= 1.1
    bottom_bounds[:, :2] *= 1.1
    top_bounds[:, 2] += (0.5 * final_height_mm - top_bounds[0, 2])
    bottom_bounds[:, 2] += (-0.5 * final_height_mm - bottom_bounds[1, 2])
    top_die = creation.box(bounds=top_bounds)
    bottom_die = creation.box(bounds=bottom_bounds)
    return boolean.difference(
        meshes=(
            boolean.difference(meshes=(mesh, top_die)),
            bottom_die,
        )
    )


def _extend_to_dimension(mesh: Any, target_dimension: float, *, axis_name: str) -> Any:
    axis_index = {"x": 0, "y": 1, "z": 2}[axis_name]
    bounds = mesh.bounds
    current_dimension = float(bounds[1, axis_index] - bounds[0, axis_index])
    extension = float(target_dimension) - current_dimension
    if abs(extension) <= 1e-9:
        return mesh
    return _extend_trimesh_along_axis(mesh, extension, axis_index)


def _extend_trimesh_along_axis(mesh: Any, abs_extension: float, axis_index: int) -> Any:
    import numpy as np

    result = mesh.copy()
    half_extension = np.float64(abs_extension / 2.0)
    vertices = result.vertices.view(np.ndarray)
    vertices[:, axis_index] = np.where(
        vertices[:, axis_index] >= 0.0,
        vertices[:, axis_index] + half_extension,
        vertices[:, axis_index] - half_extension,
    )
    return result


def _scale_trimesh(mesh: Any, x_scale: float, y_scale: float, z_scale: float) -> Any:
    import numpy as np

    matrix = np.eye(4)
    matrix[0, 0] *= float(x_scale)
    matrix[1, 1] *= float(y_scale)
    matrix[2, 2] *= float(z_scale)
    return mesh.copy().apply_transform(matrix)


def _surface_to_trimesh(surface: SurfaceMesh) -> Any:
    try:
        return surface.to_trimesh()
    except SurfaceMeshError:
        raise
    except Exception as exc:
        raise SurfaceMeshError(f"Cannot convert carried surface mesh to Trimesh: {exc}") from exc


def _geometry_polygon(geometry: GeneratedGeometry) -> Polygon:
    polygon = Polygon(geometry.cross_section_outline)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.area <= 0.0:
        raise SurfaceMeshError("Geometry cross-section polygon is empty; cannot generate STL surface")
    return polygon


def _prolongation_initial_rotations(
    *,
    template_id: str | None,
    metrics: Mapping[str, Any],
    operation_specific_parameters: Mapping[str, Any],
) -> tuple[tuple[str, float], ...]:
    raw_rotations = operation_specific_parameters.get("radial_rotations")
    rotations = _rotation_list(raw_rotations)
    if rotations:
        return rotations
    if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS:
        angle = _float(metrics.get("angle_deg"), default=_float(metrics.get("angle"), default=0.0))
        return (("y", 90.0), ("x", angle))
    angle = _float(metrics.get("angle_deg"), default=_float(metrics.get("angle"), default=0.0))
    return (("x", angle),) if angle else ()


def _rotation_list(value: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    rotations: list[tuple[str, float]] = []
    for item in value:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes, bytearray)):
            continue
        if len(item) < 2:
            continue
        try:
            rotations.append((str(item[0]), float(item[1])))
        except (TypeError, ValueError):
            continue
    return tuple(rotations)


def _float(value: object, *, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _trimesh_module() -> Any:
    try:
        import trimesh

        return trimesh
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency check
        raise SurfaceMeshError(
            "Legacy STL mesh generation requires 'trimesh[easy]'. "
            "Install backend requirements before running Pre."
        ) from exc


def _transformations_module() -> Any:
    try:
        from trimesh import transformations

        return transformations
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency check
        raise SurfaceMeshError(
            "Legacy STL mesh generation requires 'trimesh[easy]'. "
            "Install backend requirements before running Pre."
        ) from exc

"""Reusable 3D mesh primitives for preprocessor geometry."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from shapely.geometry import Polygon

from app.services.preprocessor.surface_mesh import Point3D, SurfaceMesh, SurfaceMeshError


Point2D = tuple[float, float]
RotationSpec = Sequence[tuple[str, float]]


def extruded_polygon_surface_mesh(
    outline: Sequence[Point2D],
    length: float,
    *,
    cross_section_point_count: int | None = None,
) -> SurfaceMesh:
    """Create the legacy right-prism mesh for a 2D cross-section outline."""

    polygon = Polygon(outline)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.area <= 0.0:
        raise SurfaceMeshError("Geometry cross-section polygon is empty; cannot generate STL surface")

    trimesh = _trimesh_module()
    vertices, faces = trimesh.creation.triangulate_polygon(polygon=polygon, force_vertices=True)
    mesh_obj = trimesh.creation.extrude_triangulation(vertices=vertices, faces=faces, height=float(length))
    mesh_obj.apply_translation([0.0, 0.0, -0.5 * float(length)])
    mesh_obj = rotate_trimesh_object(mesh_obj, (("x", 90.0), ("z", 90.0)))
    return SurfaceMesh.from_trimesh(
        mesh_obj,
        cross_section_point_count=cross_section_point_count if cross_section_point_count is not None else len(outline),
    )


def round_tail_radius_surface_mesh(
    *,
    diameter: float,
    tail_radius: float,
    length: float,
    circumferential_segments: int = 96,
    fillet_segments: int = 16,
) -> SurfaceMesh:
    """Create an axisymmetric cylinder mesh with rounded end edges."""

    radius = float(diameter) / 2.0
    fillet_radius = float(tail_radius)
    if radius <= 0.0:
        raise SurfaceMeshError("Round-tail billet diameter must be positive.")
    if fillet_radius <= 0.0 or fillet_radius > radius:
        raise SurfaceMeshError("Round-tail billet tail radius must be positive and not exceed billet radius.")
    if length <= 0.0:
        raise SurfaceMeshError("Round-tail billet length must be positive.")

    flat_radius = radius - fillet_radius
    half_length = float(length) / 2.0
    left_x = -half_length
    right_x = half_length
    left_cylinder_x = left_x + fillet_radius
    right_cylinder_x = right_x - fillet_radius

    vertices: list[Point3D] = []
    faces: list[tuple[int, int, int]] = []
    rings: list[list[int]] = []
    ring_keys: set[tuple[float, float]] = set()

    def add_ring(x_coord: float, ring_radius: float) -> list[int]:
        key = (round(x_coord, 9), round(ring_radius, 9))
        if key in ring_keys:
            return rings[-1]
        ring_keys.add(key)
        ring: list[int] = []
        for index in range(circumferential_segments):
            theta = 2.0 * math.pi * index / circumferential_segments
            ring.append(len(vertices))
            vertices.append(
                (
                    float(x_coord),
                    float(ring_radius) * math.cos(theta),
                    float(ring_radius) * math.sin(theta),
                )
            )
        rings.append(ring)
        return ring

    def connect_rings(first: list[int], second: list[int]) -> None:
        for index in range(circumferential_segments):
            next_index = (index + 1) % circumferential_segments
            faces.append((first[index], first[next_index], second[next_index]))
            faces.append((first[index], second[next_index], second[index]))

    def add_cap(center: int, ring: list[int], *, reverse: bool = False) -> None:
        for index in range(circumferential_segments):
            next_index = (index + 1) % circumferential_segments
            if reverse:
                faces.append((center, ring[next_index], ring[index]))
            else:
                faces.append((center, ring[index], ring[next_index]))

    left_center = len(vertices)
    vertices.append((left_x, 0.0, 0.0))
    if flat_radius > 1e-9:
        add_ring(left_x, flat_radius)

    for index in range(1, fillet_segments + 1):
        angle = math.pi - (math.pi / 2.0) * index / fillet_segments
        x_coord = left_x + fillet_radius + fillet_radius * math.cos(angle)
        ring_radius = flat_radius + fillet_radius * math.sin(angle)
        add_ring(x_coord, ring_radius)

    if right_cylinder_x > left_cylinder_x + 1e-9:
        add_ring(right_cylinder_x, radius)

    for index in range(1, fillet_segments + 1):
        angle = (math.pi / 2.0) * (1.0 - index / fillet_segments)
        x_coord = right_x - fillet_radius + fillet_radius * math.cos(angle)
        ring_radius = flat_radius + fillet_radius * math.sin(angle)
        add_ring(x_coord, ring_radius)

    right_center = len(vertices)
    vertices.append((right_x, 0.0, 0.0))

    if not rings:
        raise SurfaceMeshError("Round-tail billet mesh has no nonzero-radius rings.")

    add_cap(left_center, rings[0], reverse=True)
    for first, second in zip(rings, rings[1:]):
        connect_rings(first, second)
    add_cap(right_center, rings[-1])

    return SurfaceMesh.from_vertices_faces(
        vertices=vertices,
        faces=faces,
        cross_section_point_count=circumferential_segments,
    )


def round_tail_chamfer_surface_mesh(
    *,
    diameter: float,
    tail_chamfer: float,
    length: float,
    circumferential_segments: int = 96,
) -> SurfaceMesh:
    """Create an axisymmetric cylinder mesh with chamfered end edges."""

    radius = float(diameter) / 2.0
    chamfer = float(tail_chamfer)
    if circumferential_segments < 3:
        raise SurfaceMeshError("Round-tail chamfer mesh requires at least three circumferential segments.")
    if radius <= 0.0:
        raise SurfaceMeshError("Round-tail chamfer billet diameter must be positive.")
    if chamfer <= 0.0 or chamfer > radius:
        raise SurfaceMeshError("Round-tail chamfer must be positive and not exceed billet radius.")
    if length <= 0.0:
        raise SurfaceMeshError("Round-tail chamfer billet length must be positive.")

    flat_radius = radius - chamfer
    half_length = float(length) / 2.0
    left_x = -half_length
    right_x = half_length
    left_cylinder_x = left_x + chamfer
    right_cylinder_x = right_x - chamfer

    vertices: list[Point3D] = []
    faces: list[tuple[int, int, int]] = []
    rings: list[list[int]] = []

    def add_ring(x_coord: float, ring_radius: float) -> list[int]:
        ring: list[int] = []
        for index in range(circumferential_segments):
            theta = 2.0 * math.pi * index / circumferential_segments
            ring.append(len(vertices))
            vertices.append(
                (
                    float(x_coord),
                    float(ring_radius) * math.cos(theta),
                    float(ring_radius) * math.sin(theta),
                )
            )
        rings.append(ring)
        return ring

    def connect_rings(first: list[int], second: list[int]) -> None:
        for index in range(circumferential_segments):
            next_index = (index + 1) % circumferential_segments
            faces.append((first[index], first[next_index], second[next_index]))
            faces.append((first[index], second[next_index], second[index]))

    def add_cap(center: int, ring: list[int], *, reverse: bool = False) -> None:
        for index in range(circumferential_segments):
            next_index = (index + 1) % circumferential_segments
            if reverse:
                faces.append((center, ring[next_index], ring[index]))
            else:
                faces.append((center, ring[index], ring[next_index]))

    left_center = len(vertices)
    vertices.append((left_x, 0.0, 0.0))
    if flat_radius > 1e-9:
        add_ring(left_x, flat_radius)
    add_ring(left_cylinder_x, radius)

    if right_cylinder_x > left_cylinder_x + 1e-9:
        add_ring(right_cylinder_x, radius)

    if flat_radius > 1e-9:
        add_ring(right_x, flat_radius)

    right_center = len(vertices)
    vertices.append((right_x, 0.0, 0.0))

    add_cap(left_center, rings[0], reverse=True)
    for first, second in zip(rings, rings[1:]):
        connect_rings(first, second)
    add_cap(right_center, rings[-1])

    return SurfaceMesh.from_vertices_faces(
        vertices=vertices,
        faces=faces,
        cross_section_point_count=circumferential_segments,
    )


def rotate_trimesh_object(trimesh_obj: Any, rotations: RotationSpec) -> Any:
    """Rotate a Trimesh object around the origin."""

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
            "Legacy STL mesh rotations require 'trimesh'. Install backend requirements before running Pre."
        ) from exc

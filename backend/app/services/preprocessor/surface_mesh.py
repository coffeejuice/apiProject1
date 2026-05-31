"""Surface-mesh payloads for compiled simulation-step geometry.

The old preprocessor used Trimesh STL objects as the carried 3D billet state.
This module exposes a small JSON/API-friendly mesh container. Runtime 3D meshes
must come from explicit preprocessor mesh generators, not from hidden fallback
geometry synthesis.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import math
import os
import struct
from typing import Any


Point3D = tuple[float, float, float]
Face = tuple[int, int, int]


class SurfaceMeshError(ValueError):
    """Raised when a simulation-step geometry payload cannot produce a mesh."""


@dataclass(frozen=True, slots=True)
class SurfaceMesh:
    """Triangular surface mesh generated from one compiled geometry payload."""

    units: str
    vertices: tuple[Point3D, ...]
    faces: tuple[Face, ...]
    bounds: dict[str, float]
    cross_section_point_count: int
    surface_area_mm2: float
    volume_mm3: float

    @classmethod
    def from_vertices_faces(
        cls,
        *,
        vertices: Iterable[Point3D],
        faces: Iterable[Face],
        cross_section_point_count: int = 0,
        units: str = "mm",
    ) -> "SurfaceMesh":
        """Build a mesh payload from explicit vertices/faces."""

        vertices_tuple = tuple(
            (float(vertex[0]), float(vertex[1]), float(vertex[2]))
            for vertex in vertices
        )
        faces_tuple = tuple(
            (int(face[0]), int(face[1]), int(face[2]))
            for face in faces
        )
        return cls(
            units=units,
            vertices=vertices_tuple,
            faces=faces_tuple,
            bounds=_bounds(list(vertices_tuple)) if vertices_tuple else {},
            cross_section_point_count=cross_section_point_count,
            surface_area_mm2=_mesh_area(vertices_tuple, faces_tuple),
            volume_mm3=abs(_mesh_signed_volume(vertices_tuple, faces_tuple)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "vertices": [list(vertex) for vertex in self.vertices],
            "faces": [list(face) for face in self.faces],
            "bounds": self.bounds,
            "vertex_count": len(self.vertices),
            "face_count": len(self.faces),
            "cross_section_point_count": self.cross_section_point_count,
            "surface_area_mm2": self.surface_area_mm2,
            "volume_mm3": self.volume_mm3,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SurfaceMesh":
        """Deserialize a mesh payload produced by :meth:`to_payload`."""

        vertices = tuple(
            (float(vertex[0]), float(vertex[1]), float(vertex[2]))
            for vertex in payload.get("vertices", [])
            if isinstance(vertex, Iterable)
        )
        faces = tuple(
            (int(face[0]), int(face[1]), int(face[2]))
            for face in payload.get("faces", [])
            if isinstance(face, Iterable)
        )
        bounds = {
            str(key): float(value)
            for key, value in dict(payload.get("bounds") or {}).items()
        }
        return cls(
            units=str(payload.get("units") or "mm"),
            vertices=vertices,
            faces=faces,
            bounds=bounds or _bounds(list(vertices)),
            cross_section_point_count=int(payload.get("cross_section_point_count") or 0),
            surface_area_mm2=float(payload.get("surface_area_mm2") or 0.0),
            volume_mm3=float(payload.get("volume_mm3") or 0.0),
        )

    @classmethod
    def from_trimesh(
        cls,
        mesh: Any,
        *,
        cross_section_point_count: int = 0,
        units: str = "mm",
    ) -> "SurfaceMesh":
        """Convert a Trimesh object into the API mesh payload shape."""

        vertices_array = getattr(mesh, "vertices", [])
        faces_array = getattr(mesh, "faces", [])
        vertices: tuple[Point3D, ...] = tuple(
            (float(vertex[0]), float(vertex[1]), float(vertex[2]))
            for vertex in vertices_array
        )
        faces: tuple[Face, ...] = tuple(
            (int(face[0]), int(face[1]), int(face[2]))
            for face in faces_array
        )
        return cls(
            units=units,
            vertices=vertices,
            faces=faces,
            bounds=_bounds(list(vertices)) if vertices else {},
            cross_section_point_count=cross_section_point_count,
            surface_area_mm2=float(getattr(mesh, "area", 0.0) or 0.0),
            volume_mm3=abs(float(getattr(mesh, "volume", 0.0) or 0.0)),
        )

    @classmethod
    def from_mesh_file(
        cls,
        path: str,
        *,
        file_type: str | None = None,
        cross_section_point_count: int = 0,
        units: str = "mm",
    ) -> "SurfaceMesh":
        """Load a supported mesh file through Trimesh."""

        try:
            import trimesh
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency check
            raise SurfaceMeshError(
                "Mesh artifact loading requires 'trimesh'. Install backend requirements before running Pre."
            ) from exc

        try:
            mesh = trimesh.load(path, file_type=file_type, force="mesh", process=False)
        except Exception as exc:
            raise SurfaceMeshError(f"Cannot load mesh artifact at {path}: {type(exc).__name__}: {exc}") from exc
        if isinstance(mesh, trimesh.Scene):
            if not mesh.geometry:
                raise SurfaceMeshError(f"Mesh artifact at {path} contains an empty scene.")
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
        if not hasattr(mesh, "vertices") or not hasattr(mesh, "faces"):
            raise SurfaceMeshError(f"Mesh artifact at {path} did not load as a triangular mesh.")
        return cls.from_trimesh(
            mesh,
            cross_section_point_count=cross_section_point_count,
            units=units,
        )

    @classmethod
    def from_ply(
        cls,
        path: str,
        *,
        cross_section_point_count: int = 0,
        units: str = "mm",
    ) -> "SurfaceMesh":
        """Load the canonical binary PLY mesh artifact."""

        return cls.from_mesh_file(
            path,
            file_type="ply",
            cross_section_point_count=cross_section_point_count,
            units=units,
        )

    def to_trimesh(self) -> Any:
        """Convert this payload back to Trimesh for legacy mesh continuation."""

        try:
            import numpy as np
            import trimesh
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency check
            raise SurfaceMeshError(
                "Legacy STL continuation requires 'trimesh' and 'numpy'. "
                "Install backend requirements before running Pre."
            ) from exc

        return trimesh.Trimesh(
            vertices=np.array(self.vertices, dtype=float),
            faces=np.array(self.faces, dtype=int),
            process=False,
        )

    def write_ply(self, path: str) -> None:
        """Serialize the mesh as canonical binary PLY with shared vertices."""

        try:
            from trimesh.exchange.ply import export_ply
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency check
            raise SurfaceMeshError(
                "PLY mesh artifact writing requires 'trimesh'. Install backend requirements before running Pre."
            ) from exc

        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = export_ply(
            self.to_trimesh(),
            encoding="binary",
            vertex_normal=False,
            include_attributes=False,
        )
        with open(path, "wb") as handle:
            handle.write(data)

    def to_binary_stl(self, *, solid_name: str = "forgelab_surface") -> bytes:
        """Serialize the mesh to binary STL without introducing a trimesh runtime dependency."""

        header = solid_name.encode("ascii", errors="ignore")[:80].ljust(80, b" ")
        chunks = [header, struct.pack("<I", len(self.faces))]
        for face in self.faces:
            a, b, c = (self.vertices[index] for index in face)
            normal = _face_normal(a, b, c)
            chunks.append(struct.pack("<12fH", *normal, *a, *b, *c, 0))
        return b"".join(chunks)

    def write_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            import json

            json.dump(self.to_payload(), handle, ensure_ascii=False, indent=2)


def _face_normal(a: Point3D, b: Point3D, c: Point3D) -> Point3D:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if length <= 0.0:
        return (0.0, 0.0, 0.0)
    return (normal[0] / length, normal[1] / length, normal[2] / length)


def _mesh_area(vertices: tuple[Point3D, ...], faces: tuple[Face, ...]) -> float:
    total = 0.0
    for face in faces:
        a, b, c = (vertices[index] for index in face)
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        total += 0.5 * math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)
    return total


def _mesh_signed_volume(vertices: tuple[Point3D, ...], faces: tuple[Face, ...]) -> float:
    total = 0.0
    for face in faces:
        a, b, c = (vertices[index] for index in face)
        total += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            + a[1] * (b[2] * c[0] - b[0] * c[2])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0
    return total


def _bounds(vertices: list[Point3D]) -> dict[str, float]:
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
        "z_min": min(zs),
        "z_max": max(zs),
    }

"""Surface-mesh artifact storage for simulation-step inspection.

This module keeps heavy 3D payloads out of the hot `simulation_steps` list. Pre
writes generated meshes to canonical binary PLY files and indexes them in
`simulation_step_geometry_artifacts`. Missing artifacts are a processing error,
not a reason to synthesize replacement meshes. Compact references/summaries are
also mirrored into `simulation_steps.calculations` for compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, object_session

from app.models.workflow_runtime import SimulationStep, SimulationStepGeometryArtifact
from app.services.files.paths import build_operation_dir, get_local_runs_root, join_path
from app.services.files.storage import ensure_directory
from app.services.preprocessor.surface_mesh import SurfaceMesh, SurfaceMeshError


SurfaceKind = Literal["initial", "final"]
ArtifactFormat = Literal["ply", "json", "stl"]

CANONICAL_ARTIFACT_FORMAT = "ply"
LEGACY_ARTIFACT_FORMATS = ("json", "stl")
SURFACE_ARTIFACT_VERSION = 2
SURFACE_DIRNAME = "surface"


@dataclass(frozen=True, slots=True)
class GeneratedSurfaceArtifacts:
    meshes: dict[SurfaceKind, SurfaceMesh]
    summary: dict[str, Any]


def ensure_surface_artifacts_for_step(
    step: SimulationStep,
    *,
    document_id: int,
    max_outline_points: int,
    force: bool = False,
) -> GeneratedSurfaceArtifacts:
    """Load Pre-generated PLY artifacts for a compiled simulation step.

    `max_outline_points` and `force` are accepted for API compatibility with
    earlier builds, but this function intentionally never generates fallback
    geometry. If the Pre artifact is absent or unreadable, the caller gets
    an explicit error.
    """

    _ = (max_outline_points, force)
    generated = _load_cached_surface_artifacts(step)
    generated.summary["document_id"] = document_id
    return generated


def write_surface_artifacts_for_compiled_meshes(
    step: SimulationStep,
    *,
    document_id: int,
    meshes: dict[SurfaceKind, SurfaceMesh],
    force: bool = True,
) -> GeneratedSurfaceArtifacts | None:
    """Persist Pre-generated meshes as canonical selected-step PLY artifacts."""

    if not meshes:
        return None

    generated_at = datetime.now(timezone.utc).isoformat()
    generated_at_dt = datetime.now(timezone.utc)
    artifact_root = _artifact_root(step)
    artifact_storage_error = _safe_ensure_directory(artifact_root)

    summary: dict[str, Any] = {
        "version": SURFACE_ARTIFACT_VERSION,
        "source": "preprocessor_mesh",
        "document_id": document_id,
        "document_version_id": step.document_version_id,
        "document_operation_id": step.document_operation_id,
        "execution_order": step.execution_order,
        "generated_at": generated_at,
        "artifacts": {},
    }
    if artifact_storage_error is not None:
        summary["artifact_storage_error"] = artifact_storage_error
    db = object_session(step)
    for kind, mesh in meshes.items():
        artifact = _write_artifact_files(
            step=step,
            kind=kind,
            mesh=mesh,
            raw_geometry=mesh.to_payload(),
            artifact_root=artifact_root,
            force=force,
        )
        summary["artifacts"][kind] = artifact
        if db is not None:
            _upsert_artifact_rows(
                db,
                step=step,
                kind=kind,
                artifact=artifact,
                mesh=mesh,
                generated_at=generated_at_dt,
            )

    return GeneratedSurfaceArtifacts(meshes=dict(meshes), summary=summary)


def surface_artifact_abs_path(step: SimulationStep, kind: SurfaceKind, artifact_format: ArtifactFormat) -> str:
    """Return the absolute artifact path for a step/kind/format pair."""

    db = object_session(step)
    if db is not None:
        row = _artifact_row(db, step=step, kind=kind, artifact_format=artifact_format)
        if row is not None:
            return join_path(get_local_runs_root(), row.relative_path)
    extension = artifact_format
    return join_path(_artifact_root(step), f"{kind}_surface.{extension}")


def _load_cached_surface_artifacts(step: SimulationStep) -> GeneratedSurfaceArtifacts:
    db = object_session(step)
    if db is not None:
        generated = _load_db_surface_artifacts(db, step)
        if generated is not None:
            return generated

    summary = (step.calculations or {}).get("surface_artifacts")
    if not isinstance(summary, dict):
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + "3D surface artifacts are missing. Run the Pre worker for this document before opening 3D preview."
        )
    source = summary.get("source")
    if source not in {"legacy_preprocessor_trimesh", "preprocessor_mesh"}:
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + f"Unsupported surface artifact source={source!r}. Hidden geometry fallback is disabled; "
            "the row must be compiled by the Pre mesh path."
        )
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + "Legacy surface artifact metadata is malformed: missing 'artifacts' object."
        )

    errors: list[str] = []
    storage_error = summary.get("artifact_storage_error")
    if storage_error:
        errors.append(f"artifact storage error: {storage_error}")

    meshes: dict[SurfaceKind, SurfaceMesh] = {}
    for kind in ("initial", "final"):
        artifact = artifacts.get(kind)
        if not isinstance(artifact, dict):
            errors.append(f"{kind}: missing artifact metadata")
            continue
        write_errors = artifact.get("write_errors")
        if isinstance(write_errors, dict) and write_errors:
            errors.append(f"{kind}: artifact write errors: {write_errors}")
        files = artifact.get("files")
        if not isinstance(files, dict):
            errors.append(f"{kind}: missing artifact files metadata")
            continue
        artifact_format = _preferred_artifact_format(files)
        if artifact_format is None:
            errors.append(f"{kind}: no supported mesh artifact file is listed")
            continue
        artifact_path = surface_artifact_abs_path(step, kind, artifact_format)
        if not os.path.isfile(artifact_path):
            errors.append(f"{kind}: {artifact_format.upper()} mesh artifact file is missing at {artifact_path}")
            continue
        try:
            meshes[kind] = _load_surface_mesh_file(artifact_path, artifact_format)
        except Exception as exc:
            errors.append(
                f"{kind}: cannot read {artifact_format.upper()} mesh artifact at {artifact_path}: "
                f"{type(exc).__name__}: {exc}"
            )

    if errors:
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + "Surface artifacts are unavailable: "
            + "; ".join(errors)
        )
    if not meshes:
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + "Surface artifact metadata exists, but no initial/final mesh was loaded."
        )
    return GeneratedSurfaceArtifacts(meshes=meshes, summary=summary)


def _load_db_surface_artifacts(db: Session, step: SimulationStep) -> GeneratedSurfaceArtifacts | None:
    rows = list(
        db.scalars(
            select(SimulationStepGeometryArtifact).where(
                SimulationStepGeometryArtifact.document_operation_id == step.document_operation_id
            )
        )
    )
    if not rows:
        return None

    by_kind: dict[str, dict[str, SimulationStepGeometryArtifact]] = {}
    for row in rows:
        by_kind.setdefault(row.kind, {})[row.artifact_format] = row

    errors: list[str] = []
    meshes: dict[SurfaceKind, SurfaceMesh] = {}
    artifacts: dict[str, Any] = {}
    loaded_sources: list[str] = []
    for kind in ("initial", "final"):
        kind_rows = by_kind.get(kind, {})
        artifact_row = _preferred_artifact_row(kind_rows)
        if artifact_row is None:
            errors.append(f"{kind}: missing PLY artifact row or supported legacy artifact row")
            continue
        artifact_path = join_path(get_local_runs_root(), artifact_row.relative_path)
        if not os.path.isfile(artifact_path):
            errors.append(
                f"{kind}: {artifact_row.artifact_format.upper()} mesh artifact file is missing at {artifact_path}"
            )
            continue
        try:
            meshes[kind] = _load_surface_mesh_file(artifact_path, artifact_row.artifact_format)
        except Exception as exc:
            errors.append(
                f"{kind}: cannot read {artifact_row.artifact_format.upper()} mesh artifact at {artifact_path}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        artifact_files: dict[str, Any] = {
            artifact_row.artifact_format: _artifact_file_info_from_row(artifact_row)
        }
        artifacts[kind] = {
            "kind": kind,
            "geometry_hash": (artifact_row.artifact_metadata or {}).get("geometry_hash"),
            "summary": _artifact_summary_from_row(artifact_row),
            "files": artifact_files,
            "artifact_root": os.path.dirname(artifact_row.relative_path),
        }
        loaded_sources.append(artifact_row.source)

    if errors:
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + "Surface artifacts are unavailable from simulation_step_geometry_artifacts: "
            + "; ".join(errors)
        )
    if not meshes:
        raise SurfaceMeshError(
            _artifact_error_prefix(step)
            + "Surface artifact rows exist, but no initial/final mesh was loaded."
        )

    generated_at_values = [row.generated_at for row in rows if row.generated_at is not None]
    generated_at = max(generated_at_values).isoformat() if generated_at_values else None
    summary = {
        "version": SURFACE_ARTIFACT_VERSION,
        "source": loaded_sources[0] if loaded_sources else "preprocessor_mesh",
        "document_id": None,
        "document_version_id": step.document_version_id,
        "document_operation_id": step.document_operation_id,
        "execution_order": step.execution_order,
        "generated_at": generated_at,
        "artifacts": artifacts,
    }
    return GeneratedSurfaceArtifacts(meshes=meshes, summary=summary)


def _preferred_artifact_row(
    rows_by_format: dict[str, SimulationStepGeometryArtifact],
) -> SimulationStepGeometryArtifact | None:
    for artifact_format in (CANONICAL_ARTIFACT_FORMAT, *LEGACY_ARTIFACT_FORMATS):
        row = rows_by_format.get(artifact_format)
        if row is not None:
            return row
    return None


def _preferred_artifact_format(files: dict[str, Any]) -> ArtifactFormat | None:
    for artifact_format in (CANONICAL_ARTIFACT_FORMAT, *LEGACY_ARTIFACT_FORMATS):
        if isinstance(files.get(artifact_format), dict):
            return artifact_format  # type: ignore[return-value]
    return None


def _load_surface_mesh_file(path: str, artifact_format: ArtifactFormat | str) -> SurfaceMesh:
    if artifact_format == "ply":
        return SurfaceMesh.from_ply(path)
    if artifact_format == "json":
        with open(path, encoding="utf-8") as handle:
            return SurfaceMesh.from_payload(json.load(handle))
    if artifact_format == "stl":
        return SurfaceMesh.from_mesh_file(path, file_type="stl")
    raise SurfaceMeshError(f"Unsupported surface artifact format={artifact_format!r}")


def _artifact_error_prefix(step: SimulationStep) -> str:
    return (
        f"document_operation_id={step.document_operation_id} "
        f"document_version_id={step.document_version_id} "
        f"execution_order={step.execution_order}: "
    )


def with_surface_artifact_urls(
    summary: dict[str, Any],
    *,
    document_id: int,
    document_operation_id: int,
) -> dict[str, Any]:
    """Add route URLs to an artifact summary without persisting API paths."""

    payload = json.loads(json.dumps(summary))
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return payload

    for kind, artifact in artifacts.items():
        if kind not in {"initial", "final"} or not isinstance(artifact, dict):
            continue
        files = artifact.get("files")
        if not isinstance(files, dict):
            continue
        for artifact_format, file_info in files.items():
            if artifact_format not in {"ply", "json", "stl"} or not isinstance(file_info, dict):
                continue
            file_info["url"] = (
                f"/documents/{document_id}/simulation-steps/{document_operation_id}"
                f"/surface/artifacts/{kind}/{artifact_format}"
            )

    return payload


def _write_artifact_files(
    *,
    step: SimulationStep,
    kind: SurfaceKind,
    mesh: SurfaceMesh,
    raw_geometry: dict[str, Any] | None,
    artifact_root: str,
    force: bool,
) -> dict[str, Any]:
    ply_path = surface_artifact_abs_path(step, kind, CANONICAL_ARTIFACT_FORMAT)
    write_errors: dict[str, str] = {}

    try:
        if force or not os.path.isfile(ply_path):
            mesh.write_ply(ply_path)
    except OSError as exc:
        write_errors[CANONICAL_ARTIFACT_FORMAT] = str(exc)
    except SurfaceMeshError as exc:
        write_errors[CANONICAL_ARTIFACT_FORMAT] = str(exc)
    except Exception as exc:
        write_errors[CANONICAL_ARTIFACT_FORMAT] = f"{type(exc).__name__}: {exc}"

    root = get_local_runs_root()
    payload = {
        "kind": kind,
        "geometry_hash": _geometry_hash(raw_geometry),
        "summary": {
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces),
            "cross_section_point_count": mesh.cross_section_point_count,
            "surface_area_mm2": mesh.surface_area_mm2,
            "volume_mm3": mesh.volume_mm3,
            "bounds": mesh.bounds,
        },
        "files": {
            CANONICAL_ARTIFACT_FORMAT: _file_info(ply_path, root),
        },
        "artifact_root": _relative_path(artifact_root, root),
    }
    if write_errors:
        payload["write_errors"] = write_errors
    return payload


def _upsert_artifact_rows(
    db: Session,
    *,
    step: SimulationStep,
    kind: SurfaceKind,
    artifact: dict[str, Any],
    mesh: SurfaceMesh,
    generated_at: datetime,
) -> None:
    files = artifact.get("files") if isinstance(artifact, dict) else None
    if not isinstance(files, dict):
        return
    _delete_stale_artifact_rows(db, step=step, kind=kind)
    for artifact_format in (CANONICAL_ARTIFACT_FORMAT,):
        file_info = files.get(artifact_format)
        if not isinstance(file_info, dict):
            continue
        relative_path = str(file_info.get("relative_path") or "")
        if not relative_path:
            continue
        row = _artifact_row(db, step=step, kind=kind, artifact_format=artifact_format)
        if row is None:
            row = SimulationStepGeometryArtifact(
                document_operation_id=step.document_operation_id,
                document_version_id=step.document_version_id,
                kind=kind,
                artifact_format=artifact_format,
            )
            db.add(row)
        abs_path = join_path(get_local_runs_root(), relative_path)
        row.document_version_id = step.document_version_id
        row.source = "preprocessor_mesh"
        row.relative_path = relative_path
        row.checksum_sha256 = _file_sha256(abs_path)
        row.byte_size = int(file_info.get("size_bytes") or (os.path.getsize(abs_path) if os.path.isfile(abs_path) else 0))
        row.vertex_count = len(mesh.vertices)
        row.face_count = len(mesh.faces)
        row.cross_section_point_count = mesh.cross_section_point_count
        row.bounds = dict(mesh.bounds or {})
        row.surface_area_mm2 = mesh.surface_area_mm2
        row.volume_mm3 = mesh.volume_mm3
        row.artifact_metadata = {
            "geometry_hash": artifact.get("geometry_hash"),
            "write_errors": artifact.get("write_errors") if isinstance(artifact.get("write_errors"), dict) else {},
        }
        row.generated_at = generated_at


def _delete_stale_artifact_rows(db: Session, *, step: SimulationStep, kind: SurfaceKind) -> None:
    db.execute(
        delete(SimulationStepGeometryArtifact).where(
            SimulationStepGeometryArtifact.document_operation_id == step.document_operation_id,
            SimulationStepGeometryArtifact.kind == kind,
            SimulationStepGeometryArtifact.artifact_format.in_(LEGACY_ARTIFACT_FORMATS),
        )
    )


def _artifact_row(
    db: Session,
    *,
    step: SimulationStep,
    kind: SurfaceKind,
    artifact_format: ArtifactFormat | str,
) -> SimulationStepGeometryArtifact | None:
    return db.scalar(
        select(SimulationStepGeometryArtifact).where(
            SimulationStepGeometryArtifact.document_operation_id == step.document_operation_id,
            SimulationStepGeometryArtifact.kind == kind,
            SimulationStepGeometryArtifact.artifact_format == artifact_format,
        )
    )


def _artifact_file_info_from_row(row: SimulationStepGeometryArtifact) -> dict[str, Any]:
    return {
        "relative_path": row.relative_path,
        "size_bytes": row.byte_size,
    }


def _artifact_summary_from_row(row: SimulationStepGeometryArtifact) -> dict[str, Any]:
    return {
        "vertex_count": row.vertex_count or 0,
        "face_count": row.face_count or 0,
        "cross_section_point_count": row.cross_section_point_count or 0,
        "surface_area_mm2": row.surface_area_mm2 or 0.0,
        "volume_mm3": row.volume_mm3 or 0.0,
        "bounds": row.bounds or {},
    }


def _safe_ensure_directory(path: str) -> str | None:
    try:
        ensure_directory(path)
        return None
    except OSError as exc:
        return str(exc)


def _artifact_root(step: SimulationStep) -> str:
    return join_path(
        build_operation_dir(get_local_runs_root(), step.document_version_id, step.execution_order),
        SURFACE_DIRNAME,
        f"document_operation_{step.document_operation_id}",
    )


def _file_info(path: str, root: str) -> dict[str, Any]:
    return {
        "relative_path": _relative_path(path, root),
        "size_bytes": os.path.getsize(path) if os.path.isfile(path) else 0,
    }


def _relative_path(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def _geometry_hash(raw_geometry: dict[str, Any] | None) -> str | None:
    if raw_geometry is None:
        return None
    canonical = json.dumps(raw_geometry, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _file_sha256(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

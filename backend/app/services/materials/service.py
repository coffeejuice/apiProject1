from __future__ import annotations

from pathlib import Path

from app.models.library.material import Material as MaterialModel
from app.services.materials.errors import MaterialFileNotFoundError
from app.services.materials.models import MaterialSource, MaterialVisualPayload, ParsedMaterialFile
from app.services.materials.registry import get_parser_for_source


MATERIALS_FILES_DIR = (Path(__file__).resolve().parents[3] / "data" / "materials").resolve()

_PARSED_FILE_CACHE: dict[tuple[str, str, int, int], ParsedMaterialFile] = {}

def resolve_material_file_path(material: MaterialModel) -> Path:
    file_name = Path(material.deform_file_name or "").name.strip()
    if not file_name:
        raise MaterialFileNotFoundError(
            f"Material {material.material_id} does not define a DEFORM file name"
        )
    if file_name != (material.deform_file_name or "").strip():
        raise MaterialFileNotFoundError(
            f"Material {material.material_id} has an invalid DEFORM file name"
        )

    normalized_source = MaterialSource.DEFORM
    candidate_paths = [
        MATERIALS_FILES_DIR / normalized_source.value / file_name,
        MATERIALS_FILES_DIR / file_name,
    ]

    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate.resolve()

    lower_file_name = file_name.lower()
    for parent in (MATERIALS_FILES_DIR / normalized_source.value, MATERIALS_FILES_DIR):
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if child.is_file() and child.name.lower() == lower_file_name:
                return child.resolve()

    raise MaterialFileNotFoundError(
        f"Material source file not found for material {material.material_id}: {file_name}"
    )


def parse_material_file(material: MaterialModel) -> ParsedMaterialFile:
    parser = get_parser_for_source(MaterialSource.DEFORM)
    file_path = resolve_material_file_path(material)
    file_stat = file_path.stat()
    cache_key = (
        parser.source.value,
        str(file_path),
        file_stat.st_mtime_ns,
        file_stat.st_size,
    )

    cached = _PARSED_FILE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    parsed = parser.parse(file_path)
    _PARSED_FILE_CACHE[cache_key] = parsed
    return parsed


def get_material_visual_payload(material: MaterialModel) -> MaterialVisualPayload:
    parser = get_parser_for_source(MaterialSource.DEFORM)
    parsed = parse_material_file(material)
    return parser.build_visual_payload(material.material_id, parsed)

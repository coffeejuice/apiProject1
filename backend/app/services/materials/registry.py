from app.services.materials.errors import MaterialSourceNotSupportedError
from app.services.materials.models import MaterialSource
from app.services.materials.parsers.base import MaterialSourceParser
from app.services.materials.parsers.deform import DeformMaterialParser


_PARSERS: dict[MaterialSource, MaterialSourceParser] = {
    MaterialSource.DEFORM: DeformMaterialParser(),
}


def list_registered_parsers() -> list[MaterialSourceParser]:
    return list(_PARSERS.values())


def get_parser_for_source(source: str | MaterialSource) -> MaterialSourceParser:
    try:
        normalized_source = MaterialSource.from_value(source)
    except ValueError as exc:
        raise MaterialSourceNotSupportedError(f"Unsupported material source: {source}") from exc

    parser = _PARSERS.get(normalized_source)
    if parser is None:
        raise MaterialSourceNotSupportedError(f"Unsupported material source: {normalized_source}")

    return parser

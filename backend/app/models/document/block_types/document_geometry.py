"""Billet geometry helpers used by the semantic Document block."""

from typing import Any


# Geometry type definitions originally came from legacy operations.json
# parent type 7. They are now metadata for document_properties geometry fields,
# not standalone document block types.
GEOMETRY_TYPES: dict[str, dict[str, Any]] = {
    "68": {
        "library_name": "◯ - round D [mm]",
        "process_name": "◯ - round D {} mm",
        "labels": ["Diameter of billet [mm]:"],
        "db_columns": ["diameter"],
        "sql_types": ["NUMERIC(9, 3)"],
    },
    "69": {
        "library_name": "◯ - round D, Tail edge radius [mm]",
        "process_name": "◯ - round D {}, tail edge radius {} mm",
        "labels": ["Diameter of billet [mm]:", "Tail radius [mm]:"],
        "db_columns": ["diameter", "tail_radius"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"],
    },
    "70": {
        "library_name": "◯ - round D, Tail chamfer x 45° [mm]",
        "process_name": "◯ - round D {} mm, tail edge chamfer {} mm x 45°",
        "labels": ["Diameter of billet [mm]:", "Tail chamfer [mm]:"],
        "db_columns": ["diameter", "tail_chamfer"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"],
    },
    "71": {
        "library_name": "◯ - round L/D ratio",
        "process_name": "◯ - round L/D ratio = {}",
        "labels": ["Length/Diameter billet ratio:"],
        "db_columns": ["length_to_diameter_ratio"],
        "sql_types": ["REAL"],
    },
    "72": {
        "library_name": "⬜ - square H [mm]",
        "process_name": "⬜ - square H {} mm",
        "labels": ["Height of ⬜ billet section [mm]:"],
        "db_columns": ["side_of_square"],
        "sql_types": ["NUMERIC(9, 3)"],
    },
    "73": {
        "library_name": "⬜ - square H, Diagonal [mm]",
        "process_name": "⬜ - square H {}, diagonal {} mm",
        "labels": ["Height of ⬜ billet section [mm]:", "Diagonal of section[mm]:"],
        "db_columns": ["side_of_square", "diagonal"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"],
    },
    "74": {
        "library_name": "⬜ - square L/H ratio",
        "process_name": "⬜ - square L/H ratio = {}",
        "labels": ["Length/Height billet ratio:"],
        "db_columns": ["length_to_side_ratio"],
        "sql_types": ["REAL"],
    },
    "75": {
        "library_name": "▯ - rectangle H x W [mm]",
        "process_name": "▯ - rectangle H x W = {} x {} mm",
        "labels": ["Height of billet section [mm]:", "Width of billet section [mm]:"],
        "db_columns": ["height", "width"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"],
    },
    "76": {
        "library_name": "▯ - rectangle H/W ratio, L/Thickness ratio",
        "process_name": "▯ - rectangle H/W ratio = {}, L/Thickness ratio = {}",
        "labels": ["Height/Width of billet section:", "Length/Thickness:"],
        "db_columns": ["height_to_width_ratio", "length_to_thickness_ratio"],
        "sql_types": ["REAL", "REAL"],
    },
    "77": {
        "library_name": "▯ - rectangle H x W, Diagonal [mm]",
        "process_name": "▯ - rectangle H x W = {} x {}, diagonal {} mm",
        "labels": ["Height of billet section [mm]:", "Width of billet section [mm]:", "Diagonal of section [mm]:"],
        "db_columns": ["height", "width", "diagonal"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)", "NUMERIC(9, 3)"],
    },
    "78": {
        "library_name": "▯ - rectangle H x W, Two diagonals [mm]",
        "process_name": "▯ - rectangle H x W = {} x {}, diagonal #1 = {}, diagonal #2 = {} mm",
        "labels": [
            "Height of billet section [mm]:",
            "Width of billet section [mm]:",
            "Diagonal #1 of section [mm]:",
            "Diagonal #2 of section [mm]:",
        ],
        "db_columns": ["height", "width", "diagonal_1", "diagonal_2"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)", "NUMERIC(9, 3)", "NUMERIC(9, 3)"],
    },
    "79": {
        "library_name": "⬣ - octagon H [mm]",
        "process_name": "⬣ - octagon H = {} mm",
        "labels": ["Height of octagon section [mm]"],
        "db_columns": ["height"],
        "sql_types": ["NUMERIC(9, 3)"],
    },
}


def generate_billet_geometry_title(geometry_type_id: str, attributes: dict[str, Any]) -> str:
    """Generate a compact document title for the selected billet geometry."""

    if not geometry_type_id or geometry_type_id not in GEOMETRY_TYPES:
        return "Input Workpiece"

    geometry_type = GEOMETRY_TYPES[geometry_type_id]
    process_name = str(geometry_type["process_name"])

    values = []
    for column_name in geometry_type["db_columns"]:
        value = attributes.get(column_name, "")
        values.append(str(value) if value else "_")

    try:
        return process_name.format(*values)
    except (IndexError, KeyError):
        return str(geometry_type["library_name"])


def serialize_billet_geometry_props(props: dict[str, Any]) -> dict[str, Any]:
    """Return document geometry props enriched with geometry metadata."""

    geometry_type_id = str(props.get("geometry_type_id", "") or "")
    attributes = props.get("attributes", {})
    if not isinstance(attributes, dict):
        attributes = {}

    result: dict[str, Any] = {
        "geometry_type_id": geometry_type_id,
        "weight": props.get("weight", ""),
        "attributes": attributes,
        "billet_geometry_title": generate_billet_geometry_title(geometry_type_id, attributes),
        "available_geometry_types": [
            {
                "id": type_id,
                "name": data["library_name"],
                "labels": data["labels"],
                "columns": data["db_columns"],
            }
            for type_id, data in sorted(GEOMETRY_TYPES.items(), key=lambda item: int(item[0]))
        ],
    }

    if geometry_type_id and geometry_type_id in GEOMETRY_TYPES:
        geometry_type = GEOMETRY_TYPES[geometry_type_id]
        result["selected_geometry"] = {
            "labels": geometry_type["labels"],
            "columns": geometry_type["db_columns"],
            "library_name": geometry_type["library_name"],
        }

    return result


def validate_billet_geometry_props(props: dict[str, Any]) -> bool:
    """Validate geometry fields stored on the semantic Document block."""

    if "geometry_type_id" not in props:
        return False

    geometry_type_id = props.get("geometry_type_id")
    if geometry_type_id and str(geometry_type_id) not in GEOMETRY_TYPES:
        return False

    if "weight" in props:
        weight_value = props["weight"]
        if weight_value is not None and weight_value != "":
            try:
                float(weight_value)
            except (ValueError, TypeError):
                return False

    return True

"""Input Workpiece block type handler"""
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from uuid import UUID
from .base import BlockTypeHandler


# Geometry type definitions from operations.json (parent_type_id: 7)
GEOMETRY_TYPES = {
    "68": {
        "library_name": "◯ - round D [mm]",
        "process_name": "◯ - round D {} mm",
        "labels": ["Diameter of billet [mm]:"],
        "db_columns": ["diameter"],
        "sql_types": ["NUMERIC(9, 3)"]
    },
    "69": {
        "library_name": "◯ - round D, Tail edge radius [mm]",
        "process_name": "◯ - round D {}, tail edge radius {} mm",
        "labels": ["Diameter of billet [mm]:", "Tail radius [mm]:"],
        "db_columns": ["diameter", "tail_radius"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"]
    },
    "70": {
        "library_name": "◯ - round D, Tail chamfer x 45° [mm]",
        "process_name": "◯ - round D {} mm, tail edge chamfer {} mm x 45°",
        "labels": ["Diameter of billet [mm]:", "Tail chamfer [mm]:"],
        "db_columns": ["diameter", "tail_chamfer"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"]
    },
    "71": {
        "library_name": "◯ - round L/D ratio",
        "process_name": "◯ - round L/D ratio = {}",
        "labels": ["Length/Diameter billet ratio:"],
        "db_columns": ["length_to_diameter_ratio"],
        "sql_types": ["REAL"]
    },
    "72": {
        "library_name": "⬜ - square H [mm]",
        "process_name": "⬜ - square H {} mm",
        "labels": ["Height of ⬜ billet section [mm]:"],
        "db_columns": ["side_of_square"],
        "sql_types": ["NUMERIC(9, 3)"]
    },
    "73": {
        "library_name": "⬜ - square H, Diagonal [mm]",
        "process_name": "⬜ - square H {}, diagonal {} mm",
        "labels": ["Height of ⬜ billet section [mm]:", "Diagonal of section[mm]:"],
        "db_columns": ["side_of_square", "diagonal"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"]
    },
    "74": {
        "library_name": "⬜ - square L/H ratio",
        "process_name": "⬜ - square L/H ratio = {}",
        "labels": ["Length/Height billet ratio:"],
        "db_columns": ["length_to_side_ratio"],
        "sql_types": ["REAL"]
    },
    "75": {
        "library_name": "▯ - rectangle H x W [mm]",
        "process_name": "▯ - rectangle H x W = {} x {} mm",
        "labels": ["Height of billet section [mm]:", "Width of billet section [mm]:"],
        "db_columns": ["height", "width"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)"]
    },
    "76": {
        "library_name": "▯ - rectangle H/W ratio, L/Thickness ratio",
        "process_name": "▯ - rectangle H/W ratio = {}, L/Thickness ratio = {}",
        "labels": ["Height/Width of billet section:", "Length/Thickness:"],
        "db_columns": ["height_to_width_ratio", "length_to_thickness_ratio"],
        "sql_types": ["REAL", "REAL"]
    },
    "77": {
        "library_name": "▯ - rectangle H x W, Diagonal [mm]",
        "process_name": "▯ - rectangle H x W = {} x {}, diagonal {} mm",
        "labels": ["Height of billet section [mm]:", "Width of billet section [mm]:", "Diagonal of section [mm]:"],
        "db_columns": ["height", "width", "diagonal"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)", "NUMERIC(9, 3)"]
    },
    "78": {
        "library_name": "▯ - rectangle H x W, Two diagonals [mm]",
        "process_name": "▯ - rectangle H x W = {} x {}, diagonal #1 = {}, diagonal #2 = {} mm",
        "labels": ["Height of billet section [mm]:", "Width of billet section [mm]:", "Diagonal #1 of section [mm]:", "Diagonal #2 of section [mm]:"],
        "db_columns": ["height", "width", "diagonal_1", "diagonal_2"],
        "sql_types": ["NUMERIC(9, 3)", "NUMERIC(9, 3)", "NUMERIC(9, 3)", "NUMERIC(9, 3)"]
    },
    "79": {
        "library_name": "⬣ - octagon H [mm]",
        "process_name": "⬣ - octagon H = {} mm",
        "labels": ["Height of octagon section [mm]"],
        "db_columns": ["height"],
        "sql_types": ["NUMERIC(9, 3)"]
    }
}


def generate_input_workpiece_title(geometry_type_id: str, attributes: Dict[str, Any]) -> str:
    """Generate title based on the selected geometry type process template."""
    if not geometry_type_id or geometry_type_id not in GEOMETRY_TYPES:
        return "Input Workpiece"

    geom_type = GEOMETRY_TYPES[geometry_type_id]
    process_name = str(geom_type["process_name"])

    values = []
    for col in geom_type["db_columns"]:
        val = attributes.get(col, "")
        values.append(str(val) if val else "_")

    try:
        return process_name.format(*values)
    except (IndexError, KeyError):
        return str(geom_type["library_name"])


def serialize_input_workpiece_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Return input-workpiece props enriched with geometry metadata."""
    geometry_type_id = str(props.get("geometry_type_id", "") or "")
    attributes = props.get("attributes", {})
    if not isinstance(attributes, dict):
        attributes = {}

    result = {
        "geometry_type_id": geometry_type_id,
        "weight": props.get("weight", ""),
        "attributes": attributes,
        "input_workpiece_title": generate_input_workpiece_title(geometry_type_id, attributes),
        "available_geometry_types": [
            {
                "id": type_id,
                "name": data["library_name"],
                "labels": data["labels"],
                "columns": data["db_columns"],
            }
            for type_id, data in sorted(GEOMETRY_TYPES.items(), key=lambda x: int(x[0]))
        ],
    }

    if geometry_type_id and geometry_type_id in GEOMETRY_TYPES:
        geom_type = GEOMETRY_TYPES[geometry_type_id]
        result["selected_geometry"] = {
            "labels": geom_type["labels"],
            "columns": geom_type["db_columns"],
            "library_name": geom_type["library_name"],
        }

    return result


def validate_input_workpiece_props(props: Dict[str, Any]) -> bool:
    """Validate input-workpiece props."""
    if "geometry_type_id" not in props:
        return False

    geom_id = props.get("geometry_type_id")
    if geom_id and str(geom_id) not in GEOMETRY_TYPES:
        return False

    if "weight" in props:
        weight_val = props["weight"]
        if weight_val is not None and weight_val != "":
            try:
                float(weight_val)
            except (ValueError, TypeError):
                return False

    return True


class InputWorkpieceHandler(BlockTypeHandler):
    """
    Handler for Input Workpiece block.

    This system block defines the input workpiece parameters with dynamic geometry types.
    Each geometry type has different attributes based on operations.json definitions.

    Data is stored in the block's props field.
    """

    @property
    def block_type_name(self) -> str:
        return "input_workpiece"

    @property
    def is_system_block(self) -> bool:
        return True

    @property
    def is_removable(self) -> bool:
        return False

    @property
    def fixed_position(self) -> int:
        return 2  # After title and fixed material block

    @property
    def allow_multiple_instances(self) -> bool:
        return False  # Only one instance per document

    def get_default_props(self) -> Dict[str, Any]:
        """Return default values for input workpiece"""
        return {
            "geometry_type_id": "",  # ID from GEOMETRY_TYPES (e.g., "68", "69", etc.)
            "weight": 0.0,  # Real type
            "attributes": {}  # Dynamic attributes based on selected geometry type
        }

    def _generate_title(self, geometry_type_id: str, attributes: Dict[str, Any]) -> str:
        """Generate title based on process_name template"""
        return generate_input_workpiece_title(geometry_type_id, attributes)

    def validate_props(self, props: Dict[str, Any]) -> bool:
        """Validate input workpiece props"""
        return validate_input_workpiece_props(props)

    def serialize_for_frontend(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return props for frontend rendering with geometry type metadata.
        """
        result = serialize_input_workpiece_props(props)
        result["title"] = result.pop("input_workpiece_title")
        return result

    def on_update(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> None:
        """
        Validate and handle updates to input workpiece.
        Could be extended to trigger recalculations or validations.
        """
        props.pop("mesh_elements", None)
        if not self.validate_props(props):
            raise ValueError("Invalid input workpiece props")

    def get_editable_fields(self):
        """Return list of fields that can be edited"""
        return ["geometry_type_id", "weight", "attributes"]

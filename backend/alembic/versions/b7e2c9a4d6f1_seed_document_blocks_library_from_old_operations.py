"""seed document blocks library from old operations catalog

Revision ID: b7e2c9a4d6f1
Revises: 8d4a1f6c2b7e
Create Date: 2026-04-21 09:30:00.000000
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e2c9a4d6f1"
down_revision: Union[str, Sequence[str], None] = "8d4a1f6c2b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = [
    "type_id",
    "parent_type_id",
    "auto_create_children",
    "row",
    "process_fixed_row",
    "allow_copies",
    "text_id",
    "library_name",
    "process_name",
    "labels",
    "labels_regex",
    "db_column_names",
    "foreign_keys",
    "is_simulation",
    "is_geometry",
    "is_die_assembly",
    "is_custom_die_assembly",
    "is_press",
    "is_feed",
    "is_top_die",
    "is_bottom_die",
    "is_speed",
    "is_billet_category",
    "is_heating_category",
    "is_forming_category",
    "is_forming_operation",
    "is_surface_treatment_operation",
    "deformation_type",
    "speed_column_name",
    "tooltip_image",
    "trigger",
    "is_initialize",
    "is_accumulate",
    "is_keep",
    "is_obsolete",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_old_operations() -> list[dict[str, Any]]:
    root = _repo_root()
    candidates = [
        root / "backend" / "data" / "database_seeding" / "operations.json",
        root / "backend_old" / "forgelab" / "sql_setup" / "operations.json",
    ]
    for path in candidates:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return list(raw.values())
            if isinstance(raw, list):
                return raw
            raise RuntimeError(f"Unsupported operations catalog shape in {path}")
    raise RuntimeError("operations.json was not found in backend data or backend_old")


def _strip_legacy_language_prefix(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    parts = text.split("|")
    if len(parts) >= 3 and parts[0] == "LANGUAGE":
        return "|".join(parts[2:])
    return text


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_operation(row: dict[str, Any]) -> dict[str, Any]:
    parent_type_id = _optional_int(row.get("parent_type_id"))
    if parent_type_id == 0:
        parent_type_id = None

    return {
        "type_id": int(row["type_id"]),
        "parent_type_id": parent_type_id,
        "auto_create_children": _optional_text(row.get("auto_create_children")),
        "row": int(row.get("row") or 0),
        "process_fixed_row": _optional_int(row.get("process_fixed_row")),
        "allow_copies": bool(row.get("allow_copies", False)),
        "text_id": str(row.get("text_id") or ""),
        "library_name": _strip_legacy_language_prefix(row.get("library_name")),
        "process_name": _strip_legacy_language_prefix(row.get("process_name")),
        "labels": _optional_text(_strip_legacy_language_prefix(row.get("labels"))),
        "labels_regex": _optional_text(row.get("labels_regex")),
        "db_column_names": _optional_text(row.get("db_column_names")) or "",
        "foreign_keys": _optional_text(row.get("foreign_keys")),
        "is_simulation": bool(row.get("is_simulation", False)),
        "is_geometry": bool(row.get("is_geometry", False)),
        "is_die_assembly": bool(row.get("is_die_assembly", False)),
        "is_custom_die_assembly": bool(row.get("is_custom_die_assembly", False)),
        "is_press": bool(row.get("is_press", False)),
        "is_feed": bool(row.get("is_feed", False)),
        "is_top_die": bool(row.get("is_top_die", False)),
        "is_bottom_die": bool(row.get("is_bottom_die", False)),
        "is_speed": bool(row.get("is_speed", False)),
        "is_billet_category": bool(row.get("is_billet_category", False)),
        "is_heating_category": bool(row.get("is_heating_category", False)),
        "is_forming_category": bool(row.get("is_forming_category", False)),
        "is_forming_operation": bool(row.get("is_forming_operation", False)),
        "is_surface_treatment_operation": bool(row.get("is_surface_treatment_operation", False)),
        "deformation_type": _optional_text(row.get("deformation_type")),
        "speed_column_name": _optional_text(row.get("speed_column_name")),
        "tooltip_image": None,
        "trigger": _optional_text(row.get("trigger")),
        "is_initialize": bool(row.get("is_initialize", False)),
        "is_accumulate": bool(row.get("is_accumulate", False)),
        "is_keep": bool(row.get("is_keep", False)),
        "is_obsolete": bool(row.get("is_obsolete", False)),
    }


def upgrade() -> None:
    rows = [_normalize_operation(row) for row in _load_old_operations()]

    quoted_columns = ", ".join(f'"{column}"' for column in COLUMNS)
    values = ", ".join(f":{column}" for column in COLUMNS)
    assignments = ", ".join(
        f'"{column}" = EXCLUDED."{column}"'
        for column in COLUMNS
        if column != "type_id"
    )
    insert_sql = sa.text(
        f"""
        INSERT INTO document_blocks_library ({quoted_columns})
        VALUES ({values})
        ON CONFLICT (type_id) DO UPDATE SET {assignments}
        """
    )

    bind = op.get_bind()
    for row in rows:
        bind.execute(insert_sql, row)


def downgrade() -> None:
    rows = [_normalize_operation(row) for row in _load_old_operations()]
    children_by_parent: dict[int | None, list[int]] = {}
    for row in rows:
        children_by_parent.setdefault(row["parent_type_id"], []).append(row["type_id"])

    ordered_type_ids: list[int] = []

    def visit(type_id: int) -> None:
        for child_id in children_by_parent.get(type_id, []):
            visit(child_id)
        ordered_type_ids.append(type_id)

    for root_type_id in children_by_parent.get(None, []):
        visit(root_type_id)

    bind = op.get_bind()
    delete_sql = sa.text("DELETE FROM document_blocks_library WHERE type_id = :type_id")
    for type_id in ordered_type_ids:
        bind.execute(delete_sql, {"type_id": type_id})

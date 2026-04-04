"""convert remaining JSON columns to JSONB

Revision ID: c5d9e2a71b3f
Revises: f2b7d1c4a9e8
Create Date: 2026-02-27 11:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5d9e2a71b3f"
down_revision = "f2b7d1c4a9e8"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _column_type_name(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return str(col["type"]).lower()
    return None


def _resolve_table(preferred: str, fallback: str | None = None) -> str | None:
    if _table_exists(preferred):
        return preferred
    if fallback and _table_exists(fallback):
        return fallback
    return None


def _cast_column_to_jsonb(table_name: str, column_name: str) -> None:
    if not _table_exists(table_name) or not _column_exists(table_name, column_name):
        return
    type_name = _column_type_name(table_name, column_name)
    if type_name and "jsonb" in type_name:
        return
    op.execute(
        f"""
        ALTER TABLE {table_name}
        ALTER COLUMN {column_name} TYPE JSONB
        USING (
            CASE
                WHEN {column_name} IS NULL THEN NULL
                ELSE {column_name}::jsonb
            END
        );
        """
    )


def _cast_column_to_json(table_name: str, column_name: str) -> None:
    if not _table_exists(table_name) or not _column_exists(table_name, column_name):
        return
    type_name = _column_type_name(table_name, column_name)
    if type_name and "jsonb" not in type_name and "json" in type_name:
        return
    op.execute(
        f"""
        ALTER TABLE {table_name}
        ALTER COLUMN {column_name} TYPE JSON
        USING (
            CASE
                WHEN {column_name} IS NULL THEN NULL
                ELSE {column_name}::json
            END
        );
        """
    )


def upgrade() -> None:
    mappings = (
        (_resolve_table("blocks"), "props"),
        (_resolve_table("library"), "props"),
        (_resolve_table("die_types", "die_type"), "name"),
        (_resolve_table("die_assemblies", "die_assembly"), "name"),
        (_resolve_table("dies", "die"), "name"),
        (_resolve_table("presses", "press"), "name"),
        (_resolve_table("press_modes", "press_mode"), "name"),
    )
    for table_name, column_name in mappings:
        if table_name:
            _cast_column_to_jsonb(table_name, column_name)


def downgrade() -> None:
    mappings = (
        (_resolve_table("blocks"), "props"),
        (_resolve_table("library"), "props"),
        (_resolve_table("die_types", "die_type"), "name"),
        (_resolve_table("die_assemblies", "die_assembly"), "name"),
        (_resolve_table("dies", "die"), "name"),
        (_resolve_table("presses", "press"), "name"),
        (_resolve_table("press_modes", "press_mode"), "name"),
    )
    for table_name, column_name in mappings:
        if table_name:
            _cast_column_to_json(table_name, column_name)

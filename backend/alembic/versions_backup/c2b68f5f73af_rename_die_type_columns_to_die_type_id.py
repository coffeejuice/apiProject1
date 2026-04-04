"""rename die_type columns to die_type_id

Revision ID: c2b68f5f73af
Revises: 64a4da3a7f12
Create Date: 2026-02-26 12:55:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2b68f5f73af"
down_revision = "64a4da3a7f12"
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


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, new_name):
        return
    if not _column_exists(table_name, old_name):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};")


def upgrade() -> None:
    _rename_column_if_needed("dies", "die_type", "die_type_id")
    _rename_column_if_needed("die_assemblies", "die_type", "die_type_id")


def downgrade() -> None:
    _rename_column_if_needed("dies", "die_type_id", "die_type")
    _rename_column_if_needed("die_assemblies", "die_type_id", "die_type")

"""rename press is_obsolet to is_obsolete

Revision ID: c7f0c4f13a11
Revises: b4e1c98a6d20
Create Date: 2026-02-26 19:35:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7f0c4f13a11"
down_revision = "b4e1c98a6d20"
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
    for table_name in ("presses", "press"):
        _rename_column_if_needed(table_name, "is_obsolet", "is_obsolete")


def downgrade() -> None:
    for table_name in ("presses", "press"):
        _rename_column_if_needed(table_name, "is_obsolete", "is_obsolet")

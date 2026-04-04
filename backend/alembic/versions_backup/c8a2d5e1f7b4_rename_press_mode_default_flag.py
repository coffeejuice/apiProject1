"""rename press_modes default flag column

Revision ID: c8a2d5e1f7b4
Revises: a7d2c9e4b1f6
Create Date: 2026-02-27 14:50:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8a2d5e1f7b4"
down_revision = "a7d2c9e4b1f6"
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


def _resolve_table(preferred: str, fallback: str | None = None) -> str | None:
    if _table_exists(preferred):
        return preferred
    if fallback and _table_exists(fallback):
        return fallback
    return None


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if _column_exists(table_name, new_name):
        return
    if not _column_exists(table_name, old_name):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};")


def upgrade() -> None:
    press_modes_table = _resolve_table("press_modes", "press_mode")
    if not press_modes_table:
        return
    _rename_column_if_needed(press_modes_table, "default_press_mode", "is_default_press_mode")


def downgrade() -> None:
    press_modes_table = _resolve_table("press_modes", "press_mode")
    if not press_modes_table:
        return
    _rename_column_if_needed(press_modes_table, "is_default_press_mode", "default_press_mode")

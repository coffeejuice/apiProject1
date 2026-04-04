"""drop legacy columns from dies

Revision ID: 9d2e8f4a1c77
Revises: 7f9a4a1d2e6b
Create Date: 2026-02-26 18:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d2e8f4a1c77"
down_revision = "7f9a4a1d2e6b"
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


def _drop_col_if_exists(table_name: str, column_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, column_name):
        return
    op.drop_column(table_name, column_name)


def _add_col_if_missing(table_name: str, column_name: str, column_type: sa.types.TypeEngine) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, column_name):
        return
    op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))


def upgrade() -> None:
    for table_name in ("dies", "die"):
        _drop_col_if_exists(table_name, "die_assembly_name")
        _drop_col_if_exists(table_name, "press_die_match_code")


def downgrade() -> None:
    for table_name in ("dies", "die"):
        _add_col_if_missing(table_name, "die_assembly_name", sa.String(length=127))
        _add_col_if_missing(table_name, "press_die_match_code", sa.String(length=127))

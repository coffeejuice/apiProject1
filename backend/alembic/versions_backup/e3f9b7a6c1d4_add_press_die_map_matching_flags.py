"""add matching flags to press_die_map

Revision ID: e3f9b7a6c1d4
Revises: d1a4e6b7c9f2
Create Date: 2026-02-27 13:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3f9b7a6c1d4"
down_revision = "d1a4e6b7c9f2"
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


def _add_flag(table_name: str, column_name: str) -> None:
    if not _column_exists(table_name, column_name):
        op.add_column(
            table_name,
            sa.Column(
                column_name,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    table_name = "press_die_map"
    if not _table_exists(table_name):
        return

    _add_flag(table_name, "is_matching_as_top")
    _add_flag(table_name, "is_matching_as_bottom")
    _add_flag(table_name, "is_matching_as_left")
    _add_flag(table_name, "is_matching_as_right")


def downgrade() -> None:
    table_name = "press_die_map"
    if not _table_exists(table_name):
        return

    _drop_column_if_exists(table_name, "is_matching_as_right")
    _drop_column_if_exists(table_name, "is_matching_as_left")
    _drop_column_if_exists(table_name, "is_matching_as_bottom")
    _drop_column_if_exists(table_name, "is_matching_as_top")

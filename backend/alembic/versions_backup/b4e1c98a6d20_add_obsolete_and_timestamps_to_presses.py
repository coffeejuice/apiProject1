"""add obsolete and timestamps to presses

Revision ID: b4e1c98a6d20
Revises: 9d2e8f4a1c77
Create Date: 2026-02-26 19:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4e1c98a6d20"
down_revision = "9d2e8f4a1c77"
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


def _add_columns_for_table(table_name: str) -> None:
    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, "is_obsolet"):
        op.add_column(
            table_name,
            sa.Column(
                "is_obsolet",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if not _column_exists(table_name, "created_at"):
        op.add_column(
            table_name,
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )

    if not _column_exists(table_name, "obsolete_at"):
        op.add_column(
            table_name,
            sa.Column("obsolete_at", sa.DateTime(), nullable=True),
        )


def _drop_columns_for_table(table_name: str) -> None:
    if not _table_exists(table_name):
        return

    for col in ("obsolete_at", "created_at", "is_obsolet"):
        if _column_exists(table_name, col):
            op.drop_column(table_name, col)


def upgrade() -> None:
    for table_name in ("presses", "press"):
        _add_columns_for_table(table_name)


def downgrade() -> None:
    for table_name in ("presses", "press"):
        _drop_columns_for_table(table_name)

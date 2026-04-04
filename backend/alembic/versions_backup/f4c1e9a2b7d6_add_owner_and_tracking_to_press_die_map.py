"""add owner and tracking columns to press_die_map

Revision ID: f4c1e9a2b7d6
Revises: e3f9b7a6c1d4
Create Date: 2026-02-27 14:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4c1e9a2b7d6"
down_revision = "e3f9b7a6c1d4"
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


def _fk_exists(table_name: str, column_name: str, referred_table: str, referred_column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (
            (fk.get("constrained_columns") or []) == [column_name]
            and fk.get("referred_table") == referred_table
            and (fk.get("referred_columns") or []) == [referred_column]
        ):
            return True
    return False


def _drop_fk_constraints_for_column(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (fk.get("constrained_columns") or []) == [column_name] and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def upgrade() -> None:
    table_name = "press_die_map"
    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, "owner_user_id"):
        op.add_column(table_name, sa.Column("owner_user_id", sa.Integer(), nullable=True))
    if _table_exists("users") and not _fk_exists(table_name, "owner_user_id", "users", "user_id"):
        op.create_foreign_key(
            "fk_press_die_map_owner_user_id",
            table_name,
            "users",
            ["owner_user_id"],
            ["user_id"],
            ondelete="SET NULL",
        )

    if not _column_exists(table_name, "is_obsolete"):
        op.add_column(
            table_name,
            sa.Column(
                "is_obsolete",
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
                server_default=sa.text("now()"),
            ),
        )

    if not _column_exists(table_name, "obsolete_at"):
        op.add_column(
            table_name,
            sa.Column("obsolete_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    table_name = "press_die_map"
    if not _table_exists(table_name):
        return

    if _column_exists(table_name, "owner_user_id"):
        _drop_fk_constraints_for_column(table_name, "owner_user_id")
        op.drop_column(table_name, "owner_user_id")

    if _column_exists(table_name, "obsolete_at"):
        op.drop_column(table_name, "obsolete_at")

    if _column_exists(table_name, "created_at"):
        op.drop_column(table_name, "created_at")

    if _column_exists(table_name, "is_obsolete"):
        op.drop_column(table_name, "is_obsolete")

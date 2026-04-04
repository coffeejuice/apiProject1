"""add default_press_mode_id to press_mode

Revision ID: 0fb8c00d28ea
Revises: 9b9c2f4e7c31
Create Date: 2026-02-25 19:29:27.892634

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0fb8c00d28ea'
down_revision = '9b9c2f4e7c31'
branch_labels = None
depends_on = None

FK_NAME = "fk_press_mode_default_press_mode_id"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _fk_exists(table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    if not _table_exists("press_mode"):
        return

    if not _column_exists("press_mode", "default_press_mode_id"):
        op.add_column("press_mode", sa.Column("default_press_mode_id", sa.Integer(), nullable=True))

    # Backfill: each row points to its press's default mode, based on existing is_default_press_mode.
    op.execute(
        """
        UPDATE press_mode
        SET default_press_mode_id = NULL;
        """
    )
    op.execute(
        """
        WITH defaults AS (
            SELECT press_id, MIN(press_mode_id) AS default_press_mode_id
            FROM press_mode
            WHERE is_default_press_mode IS TRUE
              AND press_id IS NOT NULL
            GROUP BY press_id
        )
        UPDATE press_mode AS pm
        SET default_press_mode_id = defaults.default_press_mode_id
        FROM defaults
        WHERE pm.press_id = defaults.press_id;
        """
    )
    op.execute(
        """
        UPDATE press_mode
        SET default_press_mode_id = press_mode_id
        WHERE is_default_press_mode IS TRUE
          AND default_press_mode_id IS NULL;
        """
    )

    if not _fk_exists("press_mode", FK_NAME):
        op.create_foreign_key(
            FK_NAME,
            "press_mode",
            "press_mode",
            ["default_press_mode_id"],
            ["press_mode_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if not _table_exists("press_mode"):
        return

    if _fk_exists("press_mode", FK_NAME):
        op.drop_constraint(FK_NAME, "press_mode", type_="foreignkey")

    if _column_exists("press_mode", "default_press_mode_id"):
        op.drop_column("press_mode", "default_press_mode_id")

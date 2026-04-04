"""move default_press_mode_id from press_mode to press

Revision ID: 9132a4045788
Revises: 0fb8c00d28ea
Create Date: 2026-02-25 19:37:05.916180

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9132a4045788'
down_revision = '0fb8c00d28ea'
branch_labels = None
depends_on = None

OLD_FK_NAME = "fk_press_mode_default_press_mode_id"
NEW_FK_NAME = "fk_press_default_press_mode_id"


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
    if not _table_exists("press"):
        return

    if not _column_exists("press", "default_press_mode_id"):
        op.add_column("press", sa.Column("default_press_mode_id", sa.Integer(), nullable=True))

    if _table_exists("press_mode"):
        op.execute(
            """
            UPDATE press
            SET default_press_mode_id = NULL;
            """
        )
        if _column_exists("press_mode", "default_press_mode_id"):
            op.execute(
                """
                WITH defaults AS (
                    SELECT press_id, MIN(default_press_mode_id) AS default_press_mode_id
                    FROM press_mode
                    WHERE default_press_mode_id IS NOT NULL
                      AND press_id IS NOT NULL
                    GROUP BY press_id
                )
                UPDATE press AS p
                SET default_press_mode_id = defaults.default_press_mode_id
                FROM defaults
                WHERE p.press_id = defaults.press_id;
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
            UPDATE press AS p
            SET default_press_mode_id = defaults.default_press_mode_id
            FROM defaults
            WHERE p.press_id = defaults.press_id
              AND p.default_press_mode_id IS NULL;
            """
        )

    if _table_exists("press_mode") and not _fk_exists("press", NEW_FK_NAME):
        op.create_foreign_key(
            NEW_FK_NAME,
            "press",
            "press_mode",
            ["default_press_mode_id"],
            ["press_mode_id"],
            ondelete="SET NULL",
        )

    if _table_exists("press_mode"):
        if _fk_exists("press_mode", OLD_FK_NAME):
            op.drop_constraint(OLD_FK_NAME, "press_mode", type_="foreignkey")
        if _column_exists("press_mode", "default_press_mode_id"):
            op.drop_column("press_mode", "default_press_mode_id")


def downgrade() -> None:
    if not _table_exists("press_mode"):
        return

    if not _column_exists("press_mode", "default_press_mode_id"):
        op.add_column("press_mode", sa.Column("default_press_mode_id", sa.Integer(), nullable=True))

    if _table_exists("press") and _column_exists("press", "default_press_mode_id"):
        op.execute(
            """
            UPDATE press_mode AS pm
            SET default_press_mode_id = p.default_press_mode_id
            FROM press AS p
            WHERE pm.press_id = p.press_id
              AND p.default_press_mode_id IS NOT NULL;
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

    if not _fk_exists("press_mode", OLD_FK_NAME):
        op.create_foreign_key(
            OLD_FK_NAME,
            "press_mode",
            "press_mode",
            ["default_press_mode_id"],
            ["press_mode_id"],
            ondelete="SET NULL",
        )

    if _table_exists("press"):
        if _fk_exists("press", NEW_FK_NAME):
            op.drop_constraint(NEW_FK_NAME, "press", type_="foreignkey")
        if _column_exists("press", "default_press_mode_id"):
            op.drop_column("press", "default_press_mode_id")

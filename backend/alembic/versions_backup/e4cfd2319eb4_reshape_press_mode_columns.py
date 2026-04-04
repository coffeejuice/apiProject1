"""reshape press_mode columns

Revision ID: e4cfd2319eb4
Revises: c08869da1000
Create Date: 2026-02-25 20:39:08.957040

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4cfd2319eb4'
down_revision = 'c08869da1000'
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


def upgrade() -> None:
    if not _table_exists("press_mode"):
        return

    if not _column_exists("press_mode", "is_left_manipulator"):
        op.add_column(
            "press_mode",
            sa.Column(
                "is_left_manipulator",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _column_exists("press_mode", "is_right_manipulator"):
        op.add_column(
            "press_mode",
            sa.Column(
                "is_right_manipulator",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if _column_exists("press_mode", "manipulators_count"):
        op.execute(
            """
            UPDATE press_mode
            SET is_left_manipulator = COALESCE(manipulators_count, 0) >= 1,
                is_right_manipulator = COALESCE(manipulators_count, 0) >= 2;
            """
        )

    if _table_exists("press") and _column_exists("press", "default_press_mode_id") and _column_exists("press_mode", "is_default_press_mode"):
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

    for legacy_col in ("press_mode_name", "press_die_match_code", "is_default_press_mode", "manipulators_count"):
        if _column_exists("press_mode", legacy_col):
            op.drop_column("press_mode", legacy_col)


def downgrade() -> None:
    if not _table_exists("press_mode"):
        return

    if not _column_exists("press_mode", "press_mode_name"):
        op.add_column("press_mode", sa.Column("press_mode_name", sa.String(length=127), nullable=True))
    if not _column_exists("press_mode", "press_die_match_code"):
        op.add_column("press_mode", sa.Column("press_die_match_code", sa.String(length=127), nullable=True))
    if not _column_exists("press_mode", "is_default_press_mode"):
        op.add_column(
            "press_mode",
            sa.Column("is_default_press_mode", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        )
    if not _column_exists("press_mode", "manipulators_count"):
        op.add_column("press_mode", sa.Column("manipulators_count", sa.SmallInteger(), nullable=True))

    if _column_exists("press_mode", "is_left_manipulator") and _column_exists("press_mode", "is_right_manipulator"):
        op.execute(
            """
            UPDATE press_mode
            SET manipulators_count =
                CASE
                    WHEN is_right_manipulator THEN 2
                    WHEN is_left_manipulator THEN 1
                    ELSE 0
                END;
            """
        )

    if _table_exists("press") and _column_exists("press", "default_press_mode_id"):
        op.execute(
            """
            UPDATE press_mode AS pm
            SET is_default_press_mode = (p.default_press_mode_id = pm.press_mode_id)
            FROM press AS p
            WHERE pm.press_id = p.press_id;
            """
        )

    op.execute(
        """
        UPDATE press_mode
        SET press_mode_name = LEFT(COALESCE(name::text, ''), 127)
        WHERE press_mode_name IS NULL;
        """
    )
    op.execute(
        """
        UPDATE press_mode
        SET press_die_match_code = CONCAT('unknown_', press_id::text)
        WHERE press_die_match_code IS NULL;
        """
    )

    op.alter_column("press_mode", "press_mode_name", nullable=False)
    op.alter_column("press_mode", "press_die_match_code", nullable=False)

    if _column_exists("press_mode", "is_right_manipulator"):
        op.drop_column("press_mode", "is_right_manipulator")
    if _column_exists("press_mode", "is_left_manipulator"):
        op.drop_column("press_mode", "is_left_manipulator")

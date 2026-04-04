"""drop press_die_match_code from press

Revision ID: c08869da1000
Revises: 444741afaf6d
Create Date: 2026-02-25 20:34:27.826703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c08869da1000'
down_revision = '444741afaf6d'
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
    if not _table_exists("press"):
        return
    if not _column_exists("press", "press_die_match_code"):
        return
    op.drop_column("press", "press_die_match_code")


def downgrade() -> None:
    if not _table_exists("press"):
        return
    if _column_exists("press", "press_die_match_code"):
        return

    op.add_column("press", sa.Column("press_die_match_code", sa.String(length=127), nullable=True))
    if _table_exists("press_mode"):
        op.execute(
            """
            WITH press_codes AS (
                SELECT press_id, MIN(press_die_match_code) AS press_die_match_code
                FROM press_mode
                WHERE press_id IS NOT NULL
                GROUP BY press_id
            )
            UPDATE press AS p
            SET press_die_match_code = pc.press_die_match_code
            FROM press_codes AS pc
            WHERE p.press_id = pc.press_id;
            """
        )
    op.execute(
        """
        UPDATE press
        SET press_die_match_code = CONCAT('unknown_', press_id::text)
        WHERE press_die_match_code IS NULL;
        """
    )
    op.alter_column("press", "press_die_match_code", nullable=False)

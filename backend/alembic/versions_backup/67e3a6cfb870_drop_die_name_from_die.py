"""drop die_name from die

Revision ID: 67e3a6cfb870
Revises: e4cfd2319eb4
Create Date: 2026-02-25 20:50:49.107338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67e3a6cfb870'
down_revision = 'e4cfd2319eb4'
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
    if not _table_exists("die"):
        return
    if not _column_exists("die", "die_name"):
        return
    op.drop_column("die", "die_name")


def downgrade() -> None:
    if not _table_exists("die"):
        return
    if _column_exists("die", "die_name"):
        return

    op.add_column("die", sa.Column("die_name", sa.String(length=127), nullable=True))
    op.execute(
        """
        UPDATE die
        SET die_name = LEFT(
            COALESCE(NULLIF(die_template_file_name, ''), CONCAT('die_', id::text)),
            127
        )
        WHERE die_name IS NULL;
        """
    )
    op.alter_column("die", "die_name", nullable=False)

"""fix die_type sequence after seed

Revision ID: 8f6f645dd2a7
Revises: d4d2f0f4d8c1
Create Date: 2026-02-26 11:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8f6f645dd2a7"
down_revision = "d4d2f0f4d8c1"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("die_type"):
        return
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('die_type', 'id'),
            (SELECT COALESCE(MAX(id), 1) FROM die_type),
            TRUE
        );
        """
    )


def downgrade() -> None:
    # No schema rollback needed for sequence alignment.
    return

"""drop die_assembly_name from die_assembly

Revision ID: cc1de5e9bda9
Revises: 67e3a6cfb870
Create Date: 2026-02-25 20:56:16.755969

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc1de5e9bda9'
down_revision = '67e3a6cfb870'
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
    if not _table_exists("die_assembly"):
        return
    if not _column_exists("die_assembly", "die_assembly_name"):
        return
    op.drop_column("die_assembly", "die_assembly_name")


def downgrade() -> None:
    if not _table_exists("die_assembly"):
        return
    if _column_exists("die_assembly", "die_assembly_name"):
        return

    op.add_column("die_assembly", sa.Column("die_assembly_name", sa.String(length=127), nullable=True))
    op.execute(
        """
        UPDATE die_assembly
        SET die_assembly_name = LEFT(
            COALESCE(
                CASE
                    WHEN name IS NULL THEN NULL
                    WHEN json_typeof(name) = 'string' THEN trim(both '"' from name::text)
                    ELSE name::text
                END,
                CONCAT('die_assembly_', id::text)
            ),
            127
        )
        WHERE die_assembly_name IS NULL;
        """
    )
    op.alter_column("die_assembly", "die_assembly_name", nullable=False)

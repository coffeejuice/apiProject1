"""create die_assembly_die__map table

Revision ID: f3c87c8102a1
Revises: a27df7c2499f
Create Date: 2026-02-26 10:08:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3c87c8102a1"
down_revision = "a27df7c2499f"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("die_assembly_die__map"):
        return
    op.create_table(
        "die_assembly_die__map",
        sa.Column("die_assembly_id", sa.Integer(), nullable=False),
        sa.Column("die_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["die_assembly_id"], ["die_assembly.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["die_id"], ["die.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("die_assembly_id", "die_id"),
    )


def downgrade() -> None:
    if not _table_exists("die_assembly_die__map"):
        return
    op.drop_table("die_assembly_die__map")

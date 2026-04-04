"""create press_die_map table

Revision ID: a27df7c2499f
Revises: cc1de5e9bda9
Create Date: 2026-02-25 21:34:26.961779

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a27df7c2499f'
down_revision = 'cc1de5e9bda9'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("press_die_map"):
        return
    op.create_table(
        "press_die_map",
        sa.Column("press_id", sa.Integer(), nullable=False),
        sa.Column("die_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["press_id"], ["press.press_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["die_id"], ["die.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("press_id", "die_id"),
    )


def downgrade() -> None:
    if not _table_exists("press_die_map"):
        return
    op.drop_table("press_die_map")

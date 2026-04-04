"""set NOW() defaults for dies and die_assemblies created_at

Revision ID: f2b7d1c4a9e8
Revises: a6b1f9d3c2e4
Create Date: 2026-02-27 11:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2b7d1c4a9e8"
down_revision = "a6b1f9d3c2e4"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _resolve_table(preferred: str, fallback: str) -> str | None:
    if _table_exists(preferred):
        return preferred
    if _table_exists(fallback):
        return fallback
    return None


def upgrade() -> None:
    dies_table = _resolve_table("dies", "die")
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")

    if dies_table:
        op.alter_column(dies_table, "created_at", server_default=sa.text("now()"))

    if die_assemblies_table:
        op.alter_column(die_assemblies_table, "created_at", server_default=sa.text("now()"))


def downgrade() -> None:
    dies_table = _resolve_table("dies", "die")
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")

    if dies_table:
        op.alter_column(dies_table, "created_at", server_default=None)

    if die_assemblies_table:
        op.alter_column(die_assemblies_table, "created_at", server_default=None)

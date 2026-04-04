"""rename library tables to plural and drop furnace_class

Revision ID: 64a4da3a7f12
Revises: b91f0df72ef1
Create Date: 2026-02-26 12:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "64a4da3a7f12"
down_revision = "b91f0df72ef1"
branch_labels = None
depends_on = None


TABLE_RENAMES = (
    ("press_mode", "press_modes"),
    ("press", "presses"),
    ("die", "dies"),
    ("die_assembly", "die_assemblies"),
    ("die_type", "die_types"),
    ("material", "materials"),
)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _rename_table(old_name: str, new_name: str) -> None:
    old_exists = _table_exists(old_name)
    new_exists = _table_exists(new_name)
    if old_exists and not new_exists:
        op.rename_table(old_name, new_name)


def upgrade() -> None:
    for old_name, new_name in TABLE_RENAMES:
        _rename_table(old_name, new_name)

    if _table_exists("furnace_class"):
        op.execute("DROP TABLE furnace_class CASCADE;")


def downgrade() -> None:
    if not _table_exists("furnace_class"):
        op.create_table(
            "furnace_class",
            sa.Column("furnace_class_id", sa.SmallInteger(), primary_key=True, autoincrement=True),
            sa.Column("furnace_class_name", sa.String(length=1023), nullable=True),
        )

    for old_name, new_name in reversed(TABLE_RENAMES):
        _rename_table(new_name, old_name)

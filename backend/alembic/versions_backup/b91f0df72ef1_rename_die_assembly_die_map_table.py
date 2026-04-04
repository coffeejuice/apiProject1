"""rename die_assembly_die__map to die_assembly_die_map

Revision ID: b91f0df72ef1
Revises: 8f6f645dd2a7
Create Date: 2026-02-26 11:35:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b91f0df72ef1"
down_revision = "8f6f645dd2a7"
branch_labels = None
depends_on = None


OLD_TABLE_NAME = "die_assembly_die__map"
NEW_TABLE_NAME = "die_assembly_die_map"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _merge_rows(source_table: str, target_table: str) -> None:
    op.execute(
        f"""
        INSERT INTO {target_table} (die_assembly_id, die_id)
        SELECT die_assembly_id, die_id
        FROM {source_table}
        ON CONFLICT (die_assembly_id, die_id) DO NOTHING;
        """
    )


def upgrade() -> None:
    old_exists = _table_exists(OLD_TABLE_NAME)
    new_exists = _table_exists(NEW_TABLE_NAME)

    if old_exists and not new_exists:
        op.rename_table(OLD_TABLE_NAME, NEW_TABLE_NAME)
        return

    if old_exists and new_exists:
        _merge_rows(OLD_TABLE_NAME, NEW_TABLE_NAME)
        op.drop_table(OLD_TABLE_NAME)


def downgrade() -> None:
    old_exists = _table_exists(OLD_TABLE_NAME)
    new_exists = _table_exists(NEW_TABLE_NAME)

    if new_exists and not old_exists:
        op.rename_table(NEW_TABLE_NAME, OLD_TABLE_NAME)
        return

    if new_exists and old_exists:
        _merge_rows(NEW_TABLE_NAME, OLD_TABLE_NAME)
        op.drop_table(NEW_TABLE_NAME)

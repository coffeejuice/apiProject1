"""Restore simulation_step_status table name.

Revision ID: 0007_restore_step_status_name
Revises: 0006_step_payload_names
Create Date: 2026-05-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_restore_step_status_name"
down_revision: Union[str, Sequence[str], None] = "0006_step_payload_names"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("status") and not _table_exists("simulation_step_status"):
        op.execute("ALTER INDEX IF EXISTS ix_status_status RENAME TO ix_simulation_step_status_status")
        op.execute(
            "ALTER INDEX IF EXISTS ix_status_simulation_server_id "
            "RENAME TO ix_simulation_step_status_simulation_server_id"
        )
        op.rename_table("status", "simulation_step_status")


def downgrade() -> None:
    if _table_exists("simulation_step_status") and not _table_exists("status"):
        op.rename_table("simulation_step_status", "status")
        op.execute("ALTER INDEX IF EXISTS ix_simulation_step_status_status RENAME TO ix_status_status")
        op.execute(
            "ALTER INDEX IF EXISTS ix_simulation_step_status_simulation_server_id "
            "RENAME TO ix_status_simulation_server_id"
        )

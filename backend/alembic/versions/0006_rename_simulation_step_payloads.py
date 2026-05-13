"""Rename simulation step payload buckets.

Revision ID: 0006_step_payload_names
Revises: 0005_step_siblings
Create Date: 2026-05-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_step_payload_names"
down_revision: Union[str, Sequence[str], None] = "0005_step_siblings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {str(column["name"]) for column in _inspector().get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("simulation_steps")
    if "control_parameters" in columns and "pre_input" not in columns:
        op.alter_column("simulation_steps", "control_parameters", new_column_name="pre_input")
        columns.remove("control_parameters")
        columns.add("pre_input")

    if "step_specific_parameters" in columns and "pre_output" not in columns:
        op.alter_column("simulation_steps", "step_specific_parameters", new_column_name="pre_output")
        columns.remove("step_specific_parameters")
        columns.add("pre_output")

    if "metrics" in columns and "calculations" not in columns:
        op.alter_column("simulation_steps", "metrics", new_column_name="calculations")
        columns.remove("metrics")
        columns.add("calculations")

    if "parameter_values" in columns:
        if "pre_input" in columns:
            op.execute(
                sa.text(
                    """
                    UPDATE simulation_steps
                    SET pre_input =
                        CASE
                            WHEN parameter_values IS NULL OR parameter_values = '{}'::jsonb
                                THEN COALESCE(pre_input, '{}'::jsonb)
                            ELSE jsonb_build_object('compiler_values', parameter_values)
                                 || COALESCE(pre_input, '{}'::jsonb)
                        END
                    """
                )
            )
        op.drop_column("simulation_steps", "parameter_values")

    if _table_exists("simulation_step_status") and not _table_exists("status"):
        op.rename_table("simulation_step_status", "status")
        op.execute("ALTER INDEX IF EXISTS ix_simulation_step_status_status RENAME TO ix_status_status")
        op.execute(
            "ALTER INDEX IF EXISTS ix_simulation_step_status_simulation_server_id "
            "RENAME TO ix_status_simulation_server_id"
        )


def downgrade() -> None:
    columns = _column_names("simulation_steps")
    if "parameter_values" not in columns:
        op.add_column(
            "simulation_steps",
            sa.Column(
                "parameter_values",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    columns = _column_names("simulation_steps")
    if "pre_input" in columns and "control_parameters" not in columns:
        op.alter_column("simulation_steps", "pre_input", new_column_name="control_parameters")
        columns.remove("pre_input")
        columns.add("control_parameters")

    if "pre_output" in columns and "step_specific_parameters" not in columns:
        op.alter_column("simulation_steps", "pre_output", new_column_name="step_specific_parameters")
        columns.remove("pre_output")
        columns.add("step_specific_parameters")

    if "calculations" in columns and "metrics" not in columns:
        op.alter_column("simulation_steps", "calculations", new_column_name="metrics")

    if _table_exists("status") and not _table_exists("simulation_step_status"):
        op.execute("ALTER INDEX IF EXISTS ix_status_status RENAME TO ix_simulation_step_status_status")
        op.execute(
            "ALTER INDEX IF EXISTS ix_status_simulation_server_id "
            "RENAME TO ix_simulation_step_status_simulation_server_id"
        )
        op.rename_table("status", "simulation_step_status")

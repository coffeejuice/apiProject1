"""Simplify document_operations operation parameters.

Revision ID: 0002_doc_op_params
Revises: 0001_current_schema
Create Date: 2026-05-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_doc_op_params"
down_revision: Union[str, Sequence[str], None] = "0001_current_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_JSON_COLUMNS = (
    "document_properties",
    "heating_properties",
    "deformation_properties",
    "furnace_properties",
    "operation_properties",
    "effective_properties",
)


def _column_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("document_operations")}


def upgrade() -> None:
    columns = _column_names()
    if "operation_parameters" not in columns:
        op.add_column(
            "document_operations",
            sa.Column(
                "operation_parameters",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
        columns.add("operation_parameters")

    if "operation_properties" in columns:
        op.execute(
            """
            UPDATE document_operations
            SET operation_parameters = COALESCE(operation_properties -> 'target', '{}'::jsonb)
            WHERE operation_parameters = '{}'::jsonb
            """
        )

    for column_name in OLD_JSON_COLUMNS:
        if column_name in columns:
            op.drop_column("document_operations", column_name)


def downgrade() -> None:
    columns = _column_names()
    for column_name in OLD_JSON_COLUMNS:
        if column_name not in columns:
            op.add_column(
                "document_operations",
                sa.Column(
                    column_name,
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )

    columns = _column_names()
    if "operation_parameters" in columns:
        if "operation_properties" in columns:
            op.execute(
                """
                UPDATE document_operations
                SET operation_properties = jsonb_build_object('target', operation_parameters)
                """
            )
        op.drop_column("document_operations", "operation_parameters")

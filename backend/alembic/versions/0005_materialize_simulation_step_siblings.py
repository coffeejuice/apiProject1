"""Materialize simulation step siblings for document operations.

Revision ID: 0005_step_siblings
Revises: 0004_doc_op_step_pk
Create Date: 2026-05-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_step_siblings"
down_revision: Union[str, Sequence[str], None] = "0004_doc_op_step_pk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_names(table_name: str, column_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    result: set[str] = set()
    for constraint in inspector.get_foreign_keys(table_name):
        name = constraint.get("name")
        columns = constraint.get("constrained_columns", [])
        if name and column_name in columns:
            result.add(str(name))
    return result


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if "preprocess_ready" not in _column_names("simulation_steps"):
        op.add_column(
            "simulation_steps",
            sa.Column("preprocess_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    for name in _fk_names("simulation_steps", "document_operation_id"):
        op.drop_constraint(name, "simulation_steps", type_="foreignkey")
    op.create_foreign_key(
        "fk_simulation_steps_document_operation_id",
        "simulation_steps",
        "document_operations",
        ["document_operation_id"],
        ["document_operation_id"],
        ondelete="CASCADE",
    )

    op.execute(
        sa.text(
            """
            WITH latest_versions AS (
                SELECT DISTINCT ON (document_id)
                       document_id,
                       document_version_id
                FROM document_versions
                WHERE document_id IS NOT NULL
                ORDER BY document_id, document_version_id DESC
            )
            INSERT INTO simulation_steps (
                document_operation_id,
                document_version_id,
                execution_order,
                source_block_id,
                operation_template_id,
                operation_kind,
                operation_label_snapshot,
                preprocess_ready,
                block_name_snapshot,
                library_name_snapshot,
                parameter_values,
                control_parameters,
                step_specific_parameters,
                metrics
            )
            SELECT
                operation.document_operation_id,
                latest_versions.document_version_id,
                operation.operation_order,
                operation.source_block_id,
                operation.operation_template_id,
                operation.operation_kind,
                operation.label_snapshot,
                (
                    operation.parse_status = 'valid'
                    AND operation.operation_template_id IS NOT NULL
                ),
                COALESCE(
                    operation.label_snapshot,
                    operation.operation_template_id,
                    operation.operation_kind,
                    operation.source_block_type_id
                ),
                COALESCE(
                    operation.label_snapshot,
                    operation.operation_template_id,
                    operation.operation_kind,
                    operation.source_block_type_id
                ),
                '{}'::jsonb,
                '{}'::jsonb,
                '{}'::jsonb,
                '{}'::jsonb
            FROM document_operations AS operation
            JOIN latest_versions ON latest_versions.document_id = operation.document_id
            ON CONFLICT (document_operation_id) DO UPDATE
            SET
                document_version_id = EXCLUDED.document_version_id,
                execution_order = EXCLUDED.execution_order,
                source_block_id = EXCLUDED.source_block_id,
                operation_template_id = EXCLUDED.operation_template_id,
                operation_kind = EXCLUDED.operation_kind,
                operation_label_snapshot = EXCLUDED.operation_label_snapshot,
                preprocess_ready = EXCLUDED.preprocess_ready,
                block_name_snapshot = EXCLUDED.block_name_snapshot,
                library_name_snapshot = EXCLUDED.library_name_snapshot
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO simulation_step_status (
                document_operation_id,
                status,
                attempt_no,
                retry_count,
                cancel_requested,
                simulation_percent,
                runtime_artifacts
            )
            SELECT
                step.document_operation_id,
                'blocked',
                1,
                0,
                false,
                0,
                '{}'::jsonb
            FROM simulation_steps AS step
            JOIN document_operations AS operation
              ON operation.document_operation_id = step.document_operation_id
            WHERE operation.parse_status = 'valid'
              AND operation.operation_template_id IS NOT NULL
            ON CONFLICT (document_operation_id) DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM simulation_step_status AS status
            USING document_operations AS operation
            WHERE status.document_operation_id = operation.document_operation_id
              AND (
                  operation.parse_status <> 'valid'
                  OR operation.operation_template_id IS NULL
              )
            """
        )
    )


def downgrade() -> None:
    for name in _fk_names("simulation_steps", "document_operation_id"):
        op.drop_constraint(name, "simulation_steps", type_="foreignkey")
    op.create_foreign_key(
        "fk_simulation_steps_document_operation_id",
        "simulation_steps",
        "document_operations",
        ["document_operation_id"],
        ["document_operation_id"],
        ondelete="RESTRICT",
    )

    if "preprocess_ready" in _column_names("simulation_steps"):
        op.drop_column("simulation_steps", "preprocess_ready")

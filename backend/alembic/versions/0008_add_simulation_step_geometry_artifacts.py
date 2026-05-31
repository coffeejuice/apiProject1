"""Add simulation step geometry artifact table.

Revision ID: 0008_step_geometry_artifacts
Revises: 0007_restore_step_status_name
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0008_step_geometry_artifacts"
down_revision: Union[str, Sequence[str], None] = "0007_restore_step_status_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "simulation_step_geometry_artifacts"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists(TABLE_NAME):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("geometry_artifact_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_operation_id", sa.BigInteger(), nullable=False),
        sa.Column("document_version_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("artifact_format", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=63), server_default="preprocessor_mesh", nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("vertex_count", sa.Integer(), nullable=True),
        sa.Column("face_count", sa.Integer(), nullable=True),
        sa.Column("cross_section_point_count", sa.Integer(), nullable=True),
        sa.Column("bounds", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("surface_area_mm2", sa.Double(), nullable=True),
        sa.Column("volume_mm3", sa.Double(), nullable=True),
        sa.Column("artifact_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_operation_id"],
            ["simulation_steps.document_operation_id"],
            name="fk_simulation_step_geometry_artifacts_document_operation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.document_version_id"],
            name="fk_simulation_step_geometry_artifacts_document_version_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("geometry_artifact_id", name="pk_simulation_step_geometry_artifacts"),
        sa.UniqueConstraint(
            "document_operation_id",
            "kind",
            "artifact_format",
            name="uq_simulation_step_geometry_artifacts_step_kind_format",
        ),
    )
    op.create_index(
        "ix_simulation_step_geometry_artifacts_document_operation_id",
        TABLE_NAME,
        ["document_operation_id"],
    )
    op.create_index(
        "ix_simulation_step_geometry_artifacts_document_version_id",
        TABLE_NAME,
        ["document_version_id"],
    )
    op.create_index(
        "ix_simulation_step_geometry_artifacts_version_kind",
        TABLE_NAME,
        ["document_version_id", "kind"],
    )


def downgrade() -> None:
    if not _table_exists(TABLE_NAME):
        return
    op.drop_index("ix_simulation_step_geometry_artifacts_version_kind", table_name=TABLE_NAME)
    op.drop_index("ix_simulation_step_geometry_artifacts_document_version_id", table_name=TABLE_NAME)
    op.drop_index("ix_simulation_step_geometry_artifacts_document_operation_id", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)


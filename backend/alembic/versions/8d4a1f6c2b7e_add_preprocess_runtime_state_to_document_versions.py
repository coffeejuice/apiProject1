"""add preprocess runtime state to document versions

Revision ID: 8d4a1f6c2b7e
Revises: 6c2b8f1e4a9d
Create Date: 2026-04-20 15:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8d4a1f6c2b7e"
down_revision: Union[str, Sequence[str], None] = "6c2b8f1e4a9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


preprocess_status_enum = postgresql.ENUM(
    "queued",
    "running",
    "ready",
    "failed",
    name="preprocess_status_enum",
)

preprocess_status_enum_no_create = postgresql.ENUM(
    "queued",
    "running",
    "ready",
    "failed",
    name="preprocess_status_enum",
    create_type=False,
)


def upgrade() -> None:
    preprocess_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "document_versions",
        sa.Column(
            "preprocess_status",
            preprocess_status_enum_no_create,
            nullable=False,
            server_default=sa.text("'ready'"),
        ),
    )
    op.add_column("document_versions", sa.Column("preprocess_worker_name", sa.String(length=255), nullable=True))
    op.add_column("document_versions", sa.Column("preprocess_started_at", sa.DateTime(), nullable=True))
    op.add_column("document_versions", sa.Column("preprocess_finished_at", sa.DateTime(), nullable=True))
    op.add_column("document_versions", sa.Column("preprocess_error", sa.Text(), nullable=True))
    op.create_index("ix_document_versions_preprocess_status", "document_versions", ["preprocess_status"])

    op.execute(
        """
        UPDATE document_versions
        SET preprocess_status = CASE
            WHEN run_switch_status IS TRUE THEN 'queued'::preprocess_status_enum
            ELSE 'ready'::preprocess_status_enum
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_versions_preprocess_status", table_name="document_versions")
    op.drop_column("document_versions", "preprocess_error")
    op.drop_column("document_versions", "preprocess_finished_at")
    op.drop_column("document_versions", "preprocess_started_at")
    op.drop_column("document_versions", "preprocess_worker_name")
    op.drop_column("document_versions", "preprocess_status")
    preprocess_status_enum.drop(op.get_bind(), checkfirst=True)

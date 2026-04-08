"""change material name to varchar

Revision ID: d2c6e8a4b9f1
Revises: b8c2e4f6a1d0
Create Date: 2026-04-07 17:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2c6e8a4b9f1"
down_revision: Union[str, Sequence[str], None] = "b8c2e4f6a1d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "materials",
        "name",
        existing_type=sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.String(length=1023),
        existing_nullable=False,
        postgresql_using=(
            "COALESCE("
            "NULLIF(name->>'EN', ''), "
            "NULLIF(name->>'RU', ''), "
            "NULLIF(name->>'ZH_HANS', ''), "
            "NULLIF(name::text, ''), "
            "''"
            ")"
        ),
    )


def downgrade() -> None:
    op.alter_column(
        "materials",
        "name",
        existing_type=sa.String(length=1023),
        type_=sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        postgresql_using="jsonb_build_object('EN', name)",
    )

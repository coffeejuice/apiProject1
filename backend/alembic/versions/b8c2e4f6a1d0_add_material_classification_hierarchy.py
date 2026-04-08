"""add material classification hierarchy level

Revision ID: b8c2e4f6a1d0
Revises: a3d7f1c2e9b4
Create Date: 2026-04-07 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8c2e4f6a1d0"
down_revision: Union[str, Sequence[str], None] = "a3d7f1c2e9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "material_classification_axes",
        sa.Column("hierarchy_level", sa.Integer(), nullable=False, server_default=sa.text("3")),
    )

    op.execute(
        """
        UPDATE material_classification_axes
        SET hierarchy_level = CASE
            WHEN key = 'object_type' THEN 1
            WHEN key = 'composition' THEN 2
            ELSE 3
        END
        """
    )


def downgrade() -> None:
    op.drop_column("material_classification_axes", "hierarchy_level")

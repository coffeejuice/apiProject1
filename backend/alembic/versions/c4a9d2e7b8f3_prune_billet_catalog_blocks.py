"""prune old billet catalog blocks from active block library

Revision ID: c4a9d2e7b8f3
Revises: b7e2c9a4d6f1
Create Date: 2026-04-21 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4a9d2e7b8f3"
down_revision: Union[str, Sequence[str], None] = "b7e2c9a4d6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_WEIGHT_AND_BILLET_GEOMETRY_TYPE_IDS = (6, 7, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79)


def upgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks
        SET props = props - 'stock_size' - 'stock_weight'
        WHERE block_type_id = 'document_heading'
        """
    )
    op.execute(
        """
        UPDATE document_blocks
        SET props = props - 'mesh_elements'
        WHERE block_type_id = 'input_workpiece'
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id IN (6, 7, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79)
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '84|5'
        WHERE type_id = 2
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = NULL
        WHERE type_id = 7
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = FALSE
        WHERE type_id IN (6, 7, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79)
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '84|5|6|7'
        WHERE type_id = 2
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '68'
        WHERE type_id = 7
        """
    )

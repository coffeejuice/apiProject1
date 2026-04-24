"""rename full-die speed field to transversal cogging

Revision ID: f9a7c3d2e1b4
Revises: e2f4a6b8c9d1
Create Date: 2026-04-21 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f9a7c3d2e1b4"
down_revision: Union[str, Sequence[str], None] = "e2f4a6b8c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks
        SET props = jsonb_set(
                COALESCE(props, '{}'::jsonb) - 'speed_full_die',
                '{speed_transversal_cogging}',
                COALESCE(props->'speed_transversal_cogging', props->'speed_full_die'),
                TRUE
            )
        WHERE block_type_id = '26'
          AND props ? 'speed_full_die'
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Transversal cogging: V mm/s',
            process_name = 'Transversal cogging: {} mm/s',
            labels = 'Transversal cogging speed [mm/s]',
            db_column_names = 'speed_transversal_cogging'
        WHERE type_id = 14
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Deformation',
            process_name = 'Deformation: press {}, upset {} mm/s, prolong {} mm/s, transversal cogging {} mm/s, direction {}, first {} mm, next {} mm, last {} mm',
            labels = 'Press name:|Upsetting speed [mm/s]:|Prolongation speed [mm/s]:|Transversal cogging speed [mm/s]:|Select feed direction:|First feed length [mm]:|Next feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'press_id|speed_upsetting|speed_prolongation|speed_transversal_cogging|feed_direction_id|feed_first|feed_middle|feed_last'
        WHERE type_id = 26
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET speed_column_name = 'speed_transversal_cogging'
        WHERE speed_column_name = 'speed_full_die'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks
        SET props = jsonb_set(
                COALESCE(props, '{}'::jsonb) - 'speed_transversal_cogging',
                '{speed_full_die}',
                COALESCE(props->'speed_full_die', props->'speed_transversal_cogging'),
                TRUE
            )
        WHERE block_type_id = '26'
          AND props ? 'speed_transversal_cogging'
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Full die: V mm/s',
            process_name = 'Full die: {} mm/s',
            labels = 'Full die speed [mm/s]',
            db_column_names = 'speed_full_die'
        WHERE type_id = 14
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Deformation',
            process_name = 'Deformation: press {}, upset {} mm/s, prolong {} mm/s, full die {} mm/s, direction {}, first {} mm, next {} mm, last {} mm',
            labels = 'Press name:|Upsetting speed [mm/s]:|Prolongation speed [mm/s]:|Full die speed [mm/s]:|Select feed direction:|First feed length [mm]:|Next feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'press_id|speed_upsetting|speed_prolongation|speed_full_die|feed_direction_id|feed_first|feed_middle|feed_last'
        WHERE type_id = 26
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET speed_column_name = 'speed_full_die'
        WHERE speed_column_name = 'speed_transversal_cogging'
        """
    )

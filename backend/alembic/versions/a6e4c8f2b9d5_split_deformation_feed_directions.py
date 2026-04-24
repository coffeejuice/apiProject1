"""split deformation feed directions by operation family

Revision ID: a6e4c8f2b9d5
Revises: f9a7c3d2e1b4
Create Date: 2026-04-21 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a6e4c8f2b9d5"
down_revision: Union[str, Sequence[str], None] = "f9a7c3d2e1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFORMATION_COLUMNS = (
    "press_id|"
    "feed_direction_upsetting_id|speed_upsetting|"
    "feed_direction_prolongation_id|speed_prolongation|"
    "feed_direction_transversal_cogging_id|speed_transversal_cogging|"
    "feed_first|feed_middle|feed_last"
)
DEFORMATION_LABELS = (
    "Press name:|"
    "Upsetting feed direction:|Upsetting speed [mm/s]:|"
    "Prolongation feed direction:|Prolongation speed [mm/s]:|"
    "Transversal feed direction:|Transversal cogging speed [mm/s]:|"
    "First feed length [mm]:|Next feed length [mm]:|Last feed length [mm]:"
)
DEFORMATION_PROCESS_NAME = (
    "Deformation: press {}, upset feed {} speed {} mm/s, "
    "prolong feed {} speed {} mm/s, transversal feed {} speed {} mm/s, "
    "first {} mm, next {} mm, last {} mm"
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks
        SET props = jsonb_set(
                jsonb_set(
                    jsonb_set(
                        COALESCE(props, '{}'::jsonb) - 'feed_direction_id',
                        '{feed_direction_prolongation_id}',
                        COALESCE(
                            props->'feed_direction_prolongation_id',
                            props->'feed_direction_id',
                            '3'::jsonb
                        ),
                        TRUE
                    ),
                    '{feed_direction_upsetting_id}',
                    COALESCE(props->'feed_direction_upsetting_id', '3'::jsonb),
                    TRUE
                ),
                '{feed_direction_transversal_cogging_id}',
                COALESCE(props->'feed_direction_transversal_cogging_id', '3'::jsonb),
                TRUE
            )
        WHERE block_type_id = '26'
        """
    )
    op.execute(
        f"""
        UPDATE document_blocks_library
        SET
            process_name = '{DEFORMATION_PROCESS_NAME}',
            labels = '{DEFORMATION_LABELS}',
            db_column_names = '{DEFORMATION_COLUMNS}',
            foreign_keys = 'press(press_id,name)',
            is_press = TRUE,
            is_speed = TRUE,
            is_feed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 26
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks
        SET props = jsonb_set(
                COALESCE(props, '{}'::jsonb)
                    - 'feed_direction_upsetting_id'
                    - 'feed_direction_prolongation_id'
                    - 'feed_direction_transversal_cogging_id',
                '{feed_direction_id}',
                COALESCE(props->'feed_direction_prolongation_id', props->'feed_direction_id', '3'::jsonb),
                TRUE
            )
        WHERE block_type_id = '26'
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            process_name = 'Deformation: press {}, upset {} mm/s, prolong {} mm/s, transversal cogging {} mm/s, direction {}, first {} mm, next {} mm, last {} mm',
            labels = 'Press name:|Upsetting speed [mm/s]:|Prolongation speed [mm/s]:|Transversal cogging speed [mm/s]:|Select feed direction:|First feed length [mm]:|Next feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'press_id|speed_upsetting|speed_prolongation|speed_transversal_cogging|feed_direction_id|feed_first|feed_middle|feed_last',
            foreign_keys = 'press(press_id,name)||||feed_direction(feed_direction_id,feed_direction_name)|||',
            is_press = TRUE,
            is_speed = TRUE,
            is_feed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 26
        """
    )

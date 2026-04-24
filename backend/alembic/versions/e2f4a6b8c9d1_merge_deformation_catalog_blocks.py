"""merge press, speed, and feed blocks into deformation

Revision ID: e2f4a6b8c9d1
Revises: d8f1b6c3a9e2
Create Date: 2026-04-21 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e2f4a6b8c9d1"
down_revision: Union[str, Sequence[str], None] = "d8f1b6c3a9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MERGED_BLOCK_TYPE_IDS = "'26', '13', '14', '15', '16', '17', '18'"
MERGED_PROP_KEYS = (
    "'press_id', 'speed_upsetting', 'speed_prolongation', 'speed_full_die', "
    "'speed_transversal_cogging', 'feed_direction_id', 'feed_first', 'feed_middle', 'feed_last'"
)


def upgrade() -> None:
    op.execute(
        f"""
        WITH candidates AS (
            SELECT
                block_id,
                document_id,
                block_type_id,
                props,
                created_at,
                row_number() OVER (
                    PARTITION BY document_id
                    ORDER BY
                        CASE WHEN block_type_id = '26' THEN 0 ELSE 1 END,
                        created_at ASC,
                        block_id::text ASC
                ) AS target_rank
            FROM document_blocks
            WHERE block_type_id IN ({MERGED_BLOCK_TYPE_IDS})
        ),
        targets AS (
            SELECT block_id, document_id
            FROM candidates
            WHERE target_rank = 1
        ),
        source_values AS (
            SELECT
                candidates.document_id,
                CASE
                    WHEN field.key = 'speed_full_die' THEN 'speed_transversal_cogging'
                    ELSE field.key
                END AS key,
                field.value,
                CASE
                    WHEN field.key = 'speed_transversal_cogging' THEN 0
                    ELSE 1
                END AS rename_priority,
                candidates.created_at,
                candidates.block_id
            FROM candidates
            CROSS JOIN LATERAL jsonb_each(COALESCE(candidates.props, '{{}}'::jsonb)) AS field(key, value)
            WHERE field.key IN ({MERGED_PROP_KEYS})
        ),
        latest_values AS (
            SELECT DISTINCT ON (document_id, key)
                document_id,
                key,
                value
            FROM source_values
            ORDER BY document_id, key, created_at DESC, rename_priority ASC, block_id::text DESC
        ),
        merged_props AS (
            SELECT document_id, jsonb_object_agg(key, value) AS props
            FROM latest_values
            GROUP BY document_id
        )
        UPDATE document_blocks AS target
        SET
            block_type_id = '26',
            props = COALESCE(target.props, '{{}}'::jsonb) || COALESCE(merged_props.props, '{{}}'::jsonb)
        FROM targets
        LEFT JOIN merged_props ON merged_props.document_id = targets.document_id
        WHERE target.block_id = targets.block_id
        """
    )

    op.execute(
        f"""
        DO $$
        DECLARE
            old_block RECORD;
        BEGIN
            FOR old_block IN
                WITH candidates AS (
                    SELECT
                        block_id,
                        document_id,
                        block_type_id,
                        created_at,
                        row_number() OVER (
                            PARTITION BY document_id
                            ORDER BY
                                CASE WHEN block_type_id = '26' THEN 0 ELSE 1 END,
                                created_at ASC,
                                block_id::text ASC
                        ) AS target_rank
                    FROM document_blocks
                    WHERE block_type_id IN ({MERGED_BLOCK_TYPE_IDS})
                ),
                targets AS (
                    SELECT block_id, document_id
                    FROM candidates
                    WHERE target_rank = 1
                )
                SELECT candidates.block_id
                FROM candidates
                JOIN targets ON targets.document_id = candidates.document_id
                WHERE candidates.block_id <> targets.block_id
                ORDER BY candidates.created_at ASC, candidates.block_id::text ASC
            LOOP
                UPDATE documents AS document
                SET first_block_id = deleted_block.next_block_id
                FROM document_blocks AS deleted_block
                WHERE deleted_block.block_id = old_block.block_id
                  AND document.first_block_id = deleted_block.block_id;

                UPDATE document_blocks AS previous_block
                SET next_block_id = deleted_block.next_block_id
                FROM document_blocks AS deleted_block
                WHERE deleted_block.block_id = old_block.block_id
                  AND previous_block.block_id = deleted_block.previous_block_id;

                UPDATE document_blocks AS next_block
                SET previous_block_id = deleted_block.previous_block_id
                FROM document_blocks AS deleted_block
                WHERE deleted_block.block_id = old_block.block_id
                  AND next_block.block_id = deleted_block.next_block_id;

                DELETE FROM document_blocks
                WHERE block_id = old_block.block_id;
            END LOOP;
        END $$;
        """
    )

    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Deformation',
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
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '26|8'
        WHERE type_id = 24
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id IN (9, 12, 13, 14, 15, 16, 17, 18)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks
        SET props = props
            - 'speed_upsetting'
            - 'speed_prolongation'
            - 'speed_transversal_cogging'
            - 'feed_direction_id'
            - 'feed_first'
            - 'feed_middle'
            - 'feed_last'
        WHERE block_type_id = '26'
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Press',
            process_name = 'Press: {}',
            labels = 'Press name:',
            db_column_names = 'press_id',
            foreign_keys = 'press(press_id,name)',
            is_press = TRUE,
            is_speed = FALSE,
            is_feed = FALSE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 26
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '26|8|9|12'
        WHERE type_id = 24
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = FALSE
        WHERE type_id IN (9, 12, 13, 14, 15, 16, 17, 18)
        """
    )

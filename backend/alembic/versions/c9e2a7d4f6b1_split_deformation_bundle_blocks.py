"""split deformation bundle into title, press, feed, and speed blocks

Revision ID: c9e2a7d4f6b1
Revises: b2d6f8a1c4e9
Create Date: 2026-04-22 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9e2a7d4f6b1"
down_revision: Union[str, Sequence[str], None] = "b2d6f8a1c4e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            auto_create_children = '26|12|9',
            library_name = 'Deformation',
            process_name = 'Deformation',
            labels = '',
            db_column_names = '',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = FALSE,
            is_speed = FALSE,
            trigger = NULL,
            is_accumulate = FALSE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 24
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
            is_feed = FALSE,
            is_speed = FALSE,
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
        SET
            auto_create_children = '',
            library_name = 'Feed',
            process_name = 'Feed: upset {}, prolong {}, transversal {}, first {} mm, next {} mm, last {} mm',
            labels = 'Upsetting feed direction:|Prolongation feed direction:|Transversal feed direction:|First feed length [mm]:|Next feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'feed_direction_upsetting_id|feed_direction_prolongation_id|feed_direction_transversal_cogging_id|feed_first|feed_middle|feed_last',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = TRUE,
            is_speed = FALSE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 12
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            auto_create_children = '',
            library_name = 'Speed',
            process_name = 'Speed: upset {} mm/s, prolong {} mm/s, transversal {} mm/s',
            labels = 'Upsetting speed [mm/s]:|Prolongation speed [mm/s]:|Transversal speed [mm/s]:',
            db_column_names = 'speed_upsetting|speed_prolongation|speed_transversal_cogging',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = FALSE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 9
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id IN (13, 14, 15, 16, 17, 18)
        """
    )

    op.execute(
        """
        WITH targets AS (
            SELECT
                block_id,
                document_id,
                next_block_id,
                props,
                created_at,
                updated_at,
                gen_random_uuid() AS press_block_id,
                gen_random_uuid() AS feed_block_id,
                gen_random_uuid() AS speed_block_id
            FROM document_blocks
            WHERE block_type_id = '26'
              AND (
                  props ? 'speed_upsetting'
                  OR props ? 'speed_prolongation'
                  OR props ? 'speed_transversal_cogging'
                  OR props ? 'feed_direction_upsetting_id'
                  OR props ? 'feed_direction_prolongation_id'
                  OR props ? 'feed_direction_transversal_cogging_id'
                  OR props ? 'feed_first'
                  OR props ? 'feed_middle'
                  OR props ? 'feed_last'
              )
        ),
        updated_leaders AS (
            UPDATE document_blocks AS leader
            SET
                block_type_id = '24',
                props = '{}'::jsonb,
                next_block_id = targets.press_block_id
            FROM targets
            WHERE leader.block_id = targets.block_id
            RETURNING
                targets.block_id,
                targets.document_id,
                targets.next_block_id,
                targets.props,
                targets.created_at,
                targets.updated_at,
                targets.press_block_id,
                targets.feed_block_id,
                targets.speed_block_id
        ),
        inserted_press AS (
            INSERT INTO document_blocks (
                block_id,
                document_id,
                previous_block_id,
                next_block_id,
                block_type_id,
                props,
                created_at,
                updated_at,
                is_system,
                is_removable,
                fixed_position
            )
            SELECT
                press_block_id,
                document_id,
                block_id,
                feed_block_id,
                '26',
                jsonb_build_object('press_id', COALESCE(props->'press_id', '1'::jsonb)),
                created_at,
                updated_at,
                FALSE,
                TRUE,
                NULL
            FROM updated_leaders
            RETURNING block_id
        ),
        inserted_feed AS (
            INSERT INTO document_blocks (
                block_id,
                document_id,
                previous_block_id,
                next_block_id,
                block_type_id,
                props,
                created_at,
                updated_at,
                is_system,
                is_removable,
                fixed_position
            )
            SELECT
                feed_block_id,
                document_id,
                press_block_id,
                speed_block_id,
                '12',
                jsonb_build_object(
                    'feed_direction_upsetting_id', COALESCE(props->'feed_direction_upsetting_id', '3'::jsonb),
                    'feed_direction_prolongation_id', COALESCE(props->'feed_direction_prolongation_id', props->'feed_direction_id', '3'::jsonb),
                    'feed_direction_transversal_cogging_id', COALESCE(props->'feed_direction_transversal_cogging_id', '3'::jsonb),
                    'feed_first', COALESCE(props->'feed_first', '""'::jsonb),
                    'feed_middle', COALESCE(props->'feed_middle', '""'::jsonb),
                    'feed_last', COALESCE(props->'feed_last', '""'::jsonb)
                ),
                created_at,
                updated_at,
                FALSE,
                TRUE,
                NULL
            FROM updated_leaders
            RETURNING block_id
        ),
        inserted_speed AS (
            INSERT INTO document_blocks (
                block_id,
                document_id,
                previous_block_id,
                next_block_id,
                block_type_id,
                props,
                created_at,
                updated_at,
                is_system,
                is_removable,
                fixed_position
            )
            SELECT
                speed_block_id,
                document_id,
                feed_block_id,
                next_block_id,
                '9',
                jsonb_build_object(
                    'speed_upsetting', COALESCE(props->'speed_upsetting', '""'::jsonb),
                    'speed_prolongation', COALESCE(props->'speed_prolongation', '""'::jsonb),
                    'speed_transversal_cogging', COALESCE(props->'speed_transversal_cogging', '""'::jsonb)
                ),
                created_at,
                updated_at,
                FALSE,
                TRUE,
                NULL
            FROM updated_leaders
            RETURNING block_id
        )
        UPDATE document_blocks AS after_bundle
        SET previous_block_id = updated_leaders.speed_block_id
        FROM updated_leaders
        WHERE after_bundle.block_id = updated_leaders.next_block_id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        WITH bundles AS (
            SELECT
                leader.block_id AS leader_block_id,
                press.block_id AS press_block_id,
                feed.block_id AS feed_block_id,
                speed.block_id AS speed_block_id,
                speed.next_block_id AS after_bundle_block_id,
                COALESCE(press.props, '{}'::jsonb)
                    || COALESCE(feed.props, '{}'::jsonb)
                    || COALESCE(speed.props, '{}'::jsonb) AS merged_props
            FROM document_blocks AS leader
            JOIN document_blocks AS press
              ON press.block_id = leader.next_block_id
             AND press.document_id = leader.document_id
             AND press.block_type_id = '26'
            JOIN document_blocks AS feed
              ON feed.block_id = press.next_block_id
             AND feed.document_id = leader.document_id
             AND feed.block_type_id = '12'
            JOIN document_blocks AS speed
              ON speed.block_id = feed.next_block_id
             AND speed.document_id = leader.document_id
             AND speed.block_type_id = '9'
            WHERE leader.block_type_id = '24'
        ),
        updated_leaders AS (
            UPDATE document_blocks AS leader
            SET
                block_type_id = '26',
                props = bundles.merged_props,
                next_block_id = bundles.after_bundle_block_id
            FROM bundles
            WHERE leader.block_id = bundles.leader_block_id
            RETURNING bundles.press_block_id, bundles.feed_block_id, bundles.speed_block_id, bundles.after_bundle_block_id, bundles.leader_block_id
        ),
        updated_after_bundle AS (
            UPDATE document_blocks AS after_bundle
            SET previous_block_id = updated_leaders.leader_block_id
            FROM updated_leaders
            WHERE after_bundle.block_id = updated_leaders.after_bundle_block_id
            RETURNING after_bundle.block_id
        )
        DELETE FROM document_blocks
        USING updated_leaders
        WHERE document_blocks.block_id IN (
            updated_leaders.press_block_id,
            updated_leaders.feed_block_id,
            updated_leaders.speed_block_id
        )
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Deformation',
            process_name = 'Deformation: press {}, upset feed {} speed {} mm/s, prolong feed {} speed {} mm/s, transversal feed {} speed {} mm/s, first {} mm, next {} mm, last {} mm',
            labels = 'Press name:|Upsetting feed direction:|Upsetting speed [mm/s]:|Prolongation feed direction:|Prolongation speed [mm/s]:|Transversal feed direction:|Transversal cogging speed [mm/s]:|First feed length [mm]:|Next feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'press_id|feed_direction_upsetting_id|speed_upsetting|feed_direction_prolongation_id|speed_prolongation|feed_direction_transversal_cogging_id|speed_transversal_cogging|feed_first|feed_middle|feed_last',
            foreign_keys = 'presses(press_id,name)',
            is_press = TRUE,
            is_feed = TRUE,
            is_speed = TRUE,
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
        SET
            auto_create_children = '26|8',
            library_name = 'Requirements',
            process_name = 'Requirements',
            trigger = 'accumulate',
            is_accumulate = TRUE
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

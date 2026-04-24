"""reorganize deformation feed and speed bundle blocks

Revision ID: d4f8b2c7e9a1
Revises: c9e2a7d4f6b1
Create Date: 2026-04-22 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4f8b2c7e9a1"
down_revision: Union[str, Sequence[str], None] = "c9e2a7d4f6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            auto_create_children = '26|8|15|13|14',
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
            parent_type_id = 24,
            auto_create_children = '',
            row = 1,
            process_fixed_row = 1,
            allow_copies = FALSE,
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
            parent_type_id = 24,
            auto_create_children = '',
            row = 2,
            process_fixed_row = 2,
            allow_copies = FALSE,
            library_name = 'Die',
            process_name = 'Die',
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
        WHERE type_id = 8
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            parent_type_id = 24,
            auto_create_children = '',
            row = 3,
            process_fixed_row = 3,
            allow_copies = FALSE,
            library_name = 'Prolongation feed and speed',
            process_name = 'Prolongation feed and speed',
            labels = 'Feed direction:|Speed [mm/s]:|First feed length [mm]:|Middle feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'feed_direction_prolongation_id|speed_prolongation|feed_first|feed_middle|feed_last',
            foreign_keys = 'feed_direction(feed_direction_id,feed_direction_name)||||',
            is_press = FALSE,
            is_feed = TRUE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 15
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            parent_type_id = 24,
            auto_create_children = '',
            row = 4,
            process_fixed_row = 4,
            allow_copies = FALSE,
            library_name = 'Upsetting feed and speed',
            process_name = 'Upsetting feed and speed',
            labels = 'Feed direction:|Speed [mm/s]:',
            db_column_names = 'feed_direction_upsetting_id|speed_upsetting',
            foreign_keys = 'feed_direction(feed_direction_id,feed_direction_name)|',
            is_press = FALSE,
            is_feed = TRUE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 13
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            parent_type_id = 24,
            auto_create_children = '',
            row = 5,
            process_fixed_row = 5,
            allow_copies = FALSE,
            library_name = 'Transversal cogging feed and speed',
            process_name = 'Transversal cogging feed and speed',
            labels = 'Feed direction:|Speed [mm/s]:',
            db_column_names = 'feed_direction_transversal_cogging_id|speed_transversal_cogging',
            foreign_keys = 'feed_direction(feed_direction_id,feed_direction_name)|',
            is_press = FALSE,
            is_feed = TRUE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 14
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id IN (9, 12, 16, 17, 18)
        """
    )

    op.execute(
        """
        CREATE TEMP TABLE tmp_deformation_bundle_reorg ON COMMIT DROP AS
        SELECT
            leader.block_id AS leader_block_id,
            leader.document_id AS document_id,
            press.block_id AS press_block_id,
            feed.block_id AS feed_block_id,
            speed.block_id AS speed_block_id,
            speed.next_block_id AS after_bundle_block_id,
            COALESCE(feed.props, '{}'::jsonb) AS feed_props,
            COALESCE(speed.props, '{}'::jsonb) AS speed_props,
            leader.created_at AS created_at,
            leader.updated_at AS updated_at,
            gen_random_uuid() AS die_block_id,
            gen_random_uuid() AS prolongation_block_id,
            gen_random_uuid() AS upsetting_block_id,
            gen_random_uuid() AS transversal_block_id
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
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS leader
        SET
            props = '{}'::jsonb,
            next_block_id = tmp.press_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE leader.block_id = tmp.leader_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS press
        SET previous_block_id = tmp.leader_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE press.block_id = tmp.press_block_id
        """
    )
    op.execute(
        """
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
            die_block_id,
            document_id,
            press_block_id,
            NULL,
            '8',
            '{}'::jsonb,
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_bundle_reorg
        """
    )
    op.execute(
        """
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
            prolongation_block_id,
            document_id,
            die_block_id,
            NULL,
            '15',
            jsonb_build_object(
                'feed_direction_prolongation_id', COALESCE(feed_props->'feed_direction_prolongation_id', '3'::jsonb),
                'speed_prolongation', COALESCE(speed_props->'speed_prolongation', '""'::jsonb),
                'feed_first', COALESCE(feed_props->'feed_first', '""'::jsonb),
                'feed_middle', COALESCE(feed_props->'feed_middle', '""'::jsonb),
                'feed_last', COALESCE(feed_props->'feed_last', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_bundle_reorg
        """
    )
    op.execute(
        """
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
            upsetting_block_id,
            document_id,
            prolongation_block_id,
            NULL,
            '13',
            jsonb_build_object(
                'feed_direction_upsetting_id', COALESCE(feed_props->'feed_direction_upsetting_id', '3'::jsonb),
                'speed_upsetting', COALESCE(speed_props->'speed_upsetting', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_bundle_reorg
        """
    )
    op.execute(
        """
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
            transversal_block_id,
            document_id,
            upsetting_block_id,
            after_bundle_block_id,
            '14',
            jsonb_build_object(
                'feed_direction_transversal_cogging_id', COALESCE(feed_props->'feed_direction_transversal_cogging_id', '3'::jsonb),
                'speed_transversal_cogging', COALESCE(speed_props->'speed_transversal_cogging', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_bundle_reorg
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS press
        SET next_block_id = tmp.die_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE press.block_id = tmp.press_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS die
        SET next_block_id = tmp.prolongation_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE die.block_id = tmp.die_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS prolongation
        SET next_block_id = tmp.upsetting_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE prolongation.block_id = tmp.prolongation_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS upsetting
        SET next_block_id = tmp.transversal_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE upsetting.block_id = tmp.upsetting_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS after_bundle
        SET previous_block_id = tmp.transversal_block_id
        FROM tmp_deformation_bundle_reorg AS tmp
        WHERE after_bundle.block_id = tmp.after_bundle_block_id
        """
    )
    op.execute(
        """
        DELETE FROM document_blocks AS old_block
        USING tmp_deformation_bundle_reorg AS tmp
        WHERE old_block.block_id IN (tmp.feed_block_id, tmp.speed_block_id)
        """
    )


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TEMP TABLE tmp_deformation_bundle_restore ON COMMIT DROP AS
        SELECT
            leader.block_id AS leader_block_id,
            leader.document_id AS document_id,
            press.block_id AS press_block_id,
            die.block_id AS die_block_id,
            prolongation.block_id AS prolongation_block_id,
            upsetting.block_id AS upsetting_block_id,
            transversal.block_id AS transversal_block_id,
            transversal.next_block_id AS after_bundle_block_id,
            COALESCE(prolongation.props, '{}'::jsonb) AS prolongation_props,
            COALESCE(upsetting.props, '{}'::jsonb) AS upsetting_props,
            COALESCE(transversal.props, '{}'::jsonb) AS transversal_props,
            leader.created_at AS created_at,
            leader.updated_at AS updated_at,
            gen_random_uuid() AS feed_block_id,
            gen_random_uuid() AS speed_block_id
        FROM document_blocks AS leader
        JOIN document_blocks AS press
          ON press.block_id = leader.next_block_id
         AND press.document_id = leader.document_id
         AND press.block_type_id = '26'
        JOIN document_blocks AS die
          ON die.block_id = press.next_block_id
         AND die.document_id = leader.document_id
         AND die.block_type_id = '8'
        JOIN document_blocks AS prolongation
          ON prolongation.block_id = die.next_block_id
         AND prolongation.document_id = leader.document_id
         AND prolongation.block_type_id = '15'
        JOIN document_blocks AS upsetting
          ON upsetting.block_id = prolongation.next_block_id
         AND upsetting.document_id = leader.document_id
         AND upsetting.block_type_id = '13'
        JOIN document_blocks AS transversal
          ON transversal.block_id = upsetting.next_block_id
         AND transversal.document_id = leader.document_id
         AND transversal.block_type_id = '14'
        WHERE leader.block_type_id = '24'
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS leader
        SET
            props = '{}'::jsonb,
            next_block_id = tmp.press_block_id
        FROM tmp_deformation_bundle_restore AS tmp
        WHERE leader.block_id = tmp.leader_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS press
        SET previous_block_id = tmp.leader_block_id
        FROM tmp_deformation_bundle_restore AS tmp
        WHERE press.block_id = tmp.press_block_id
        """
    )
    op.execute(
        """
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
            NULL,
            '12',
            jsonb_build_object(
                'feed_direction_upsetting_id', COALESCE(upsetting_props->'feed_direction_upsetting_id', '3'::jsonb),
                'feed_direction_prolongation_id', COALESCE(prolongation_props->'feed_direction_prolongation_id', '3'::jsonb),
                'feed_direction_transversal_cogging_id', COALESCE(transversal_props->'feed_direction_transversal_cogging_id', '3'::jsonb),
                'feed_first', COALESCE(prolongation_props->'feed_first', '""'::jsonb),
                'feed_middle', COALESCE(prolongation_props->'feed_middle', '""'::jsonb),
                'feed_last', COALESCE(prolongation_props->'feed_last', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_bundle_restore
        """
    )
    op.execute(
        """
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
            after_bundle_block_id,
            '9',
            jsonb_build_object(
                'speed_upsetting', COALESCE(upsetting_props->'speed_upsetting', '""'::jsonb),
                'speed_prolongation', COALESCE(prolongation_props->'speed_prolongation', '""'::jsonb),
                'speed_transversal_cogging', COALESCE(transversal_props->'speed_transversal_cogging', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_bundle_restore
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS press
        SET next_block_id = tmp.feed_block_id
        FROM tmp_deformation_bundle_restore AS tmp
        WHERE press.block_id = tmp.press_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS feed
        SET next_block_id = tmp.speed_block_id
        FROM tmp_deformation_bundle_restore AS tmp
        WHERE feed.block_id = tmp.feed_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS after_bundle
        SET previous_block_id = tmp.speed_block_id
        FROM tmp_deformation_bundle_restore AS tmp
        WHERE after_bundle.block_id = tmp.after_bundle_block_id
        """
    )
    op.execute(
        """
        DELETE FROM document_blocks AS old_block
        USING tmp_deformation_bundle_restore AS tmp
        WHERE old_block.block_id IN (
            tmp.die_block_id,
            tmp.prolongation_block_id,
            tmp.upsetting_block_id,
            tmp.transversal_block_id
        )
        """
    )
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
            parent_type_id = 24,
            auto_create_children = '',
            row = 1,
            process_fixed_row = 1,
            allow_copies = FALSE,
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
            parent_type_id = 24,
            auto_create_children = '19',
            row = 2,
            process_fixed_row = 2,
            allow_copies = FALSE,
            library_name = 'Die',
            process_name = 'Die',
            labels = '',
            db_column_names = '',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = FALSE,
            is_speed = FALSE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 8
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            parent_type_id = 24,
            auto_create_children = '',
            row = 4,
            process_fixed_row = 4,
            allow_copies = FALSE,
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
            parent_type_id = 24,
            auto_create_children = '',
            row = 3,
            process_fixed_row = 3,
            allow_copies = FALSE,
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
        SET
            parent_type_id = 9,
            auto_create_children = '',
            row = 1,
            process_fixed_row = NULL,
            allow_copies = TRUE,
            library_name = 'Upsetting: V mm/s',
            process_name = 'Upsetting: {} mm/s',
            labels = 'Upsetting speed [mm/s]',
            db_column_names = 'speed_upsetting',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = FALSE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = TRUE
        WHERE type_id = 13
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            parent_type_id = 9,
            auto_create_children = '',
            row = 2,
            process_fixed_row = NULL,
            allow_copies = TRUE,
            library_name = 'Prolongation: V mm/s',
            process_name = 'Prolongation: {} mm/s',
            labels = 'Prolongation speed [mm/s]',
            db_column_names = 'speed_prolongation',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = FALSE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = TRUE
        WHERE type_id = 15
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            parent_type_id = 9,
            auto_create_children = '',
            row = 4,
            process_fixed_row = NULL,
            allow_copies = TRUE,
            library_name = 'Transversal cogging: V mm/s',
            process_name = 'Transversal cogging: {} mm/s',
            labels = 'Transversal cogging speed [mm/s]',
            db_column_names = 'speed_transversal_cogging',
            foreign_keys = '',
            is_press = FALSE,
            is_feed = FALSE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = TRUE
        WHERE type_id = 14
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id IN (16, 17, 18)
        """
    )

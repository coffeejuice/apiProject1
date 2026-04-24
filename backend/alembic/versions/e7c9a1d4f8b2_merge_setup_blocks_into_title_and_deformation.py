"""merge setup blocks into title and deformation blocks

Revision ID: e7c9a1d4f8b2
Revises: d4f8b2c7e9a1
Create Date: 2026-04-22 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7c9a1d4f8b2"
down_revision: Union[str, Sequence[str], None] = "d4f8b2c7e9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            auto_create_children = '',
            labels = 'Press name:|Prolongation feed direction:|Prolongation speed [mm/s]:|Upsetting feed direction:|Upsetting speed [mm/s]:|Transversal cogging feed direction:|Transversal cogging speed [mm/s]:|First feed length [mm]:|Middle feed length [mm]:|Last feed length [mm]:',
            db_column_names = 'press_id|feed_direction_prolongation_id|speed_prolongation|feed_direction_upsetting_id|speed_upsetting|feed_direction_transversal_cogging_id|speed_transversal_cogging|feed_first|feed_middle|feed_last',
            foreign_keys = 'presses(press_id,name)|feed_direction(feed_direction_id,feed_direction_name)||feed_direction(feed_direction_id,feed_direction_name)||feed_direction(feed_direction_id,feed_direction_name)||||',
            is_press = TRUE,
            is_feed = TRUE,
            is_speed = TRUE,
            trigger = 'accumulate',
            is_accumulate = TRUE,
            is_keep = FALSE,
            is_obsolete = FALSE
        WHERE type_id = 24
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id IN (5, 84, 26, 8, 15, 13, 14)
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            heading RECORD;
            current_id UUID;
            current_block RECORD;
            delete_ids UUID[];
            merged_props JSONB;
            default_material_id INTEGER;
        BEGIN
            FOR heading IN
                SELECT *
                FROM document_blocks
                WHERE block_type_id = 'document_heading'
            LOOP
                merged_props := COALESCE(heading.props, '{}'::jsonb)
                    - 'stock_size'
                    - 'stock_weight'
                    - 'available_geometry_types'
                    - 'selected_geometry'
                    - 'input_workpiece_title'
                    - 'title'
                    - 'operation_type'
                    - 'editable_fields'
                    - 'field_limits';
                delete_ids := ARRAY[]::uuid[];
                current_id := heading.next_block_id;

                WHILE current_id IS NOT NULL LOOP
                    SELECT *
                    INTO current_block
                    FROM document_blocks
                    WHERE block_id = current_id
                      AND document_id = heading.document_id;

                    EXIT WHEN NOT FOUND;
                    EXIT WHEN current_block.block_type_id NOT IN ('5', 'input_workpiece', '84');

                    IF current_block.block_type_id = '5' AND current_block.props ? 'material_id' THEN
                        merged_props := jsonb_set(
                            merged_props,
                            '{material_id}',
                            current_block.props->'material_id',
                            TRUE
                        );
                    ELSIF current_block.block_type_id = 'input_workpiece' THEN
                        IF current_block.props ? 'geometry_type_id' THEN
                            merged_props := jsonb_set(
                                merged_props,
                                '{geometry_type_id}',
                                current_block.props->'geometry_type_id',
                                TRUE
                            );
                        END IF;
                        IF current_block.props ? 'weight' THEN
                            merged_props := jsonb_set(
                                merged_props,
                                '{weight}',
                                current_block.props->'weight',
                                TRUE
                            );
                        END IF;
                        IF current_block.props ? 'attributes' THEN
                            merged_props := jsonb_set(
                                merged_props,
                                '{attributes}',
                                current_block.props->'attributes',
                                TRUE
                            );
                        END IF;
                    ELSIF current_block.block_type_id = '84' AND current_block.props ? 'mesh_elements' THEN
                        merged_props := jsonb_set(
                            merged_props,
                            '{mesh_elements}',
                            current_block.props->'mesh_elements',
                            TRUE
                        );
                    END IF;

                    delete_ids := array_append(delete_ids, current_id);
                    current_id := current_block.next_block_id;
                END LOOP;

                IF NOT (merged_props ? 'material_id') THEN
                    default_material_id := NULL;
                    SELECT projects.material_id
                    INTO default_material_id
                    FROM documents
                    JOIN projects ON projects.project_id = documents.project_id
                    WHERE documents.document_id = heading.document_id;

                    merged_props := jsonb_set(
                        merged_props,
                        '{material_id}',
                        COALESCE(to_jsonb(default_material_id), to_jsonb(''::text)),
                        TRUE
                    );
                END IF;
                IF NOT (merged_props ? 'geometry_type_id') THEN
                    merged_props := jsonb_set(merged_props, '{geometry_type_id}', to_jsonb(''::text), TRUE);
                END IF;
                IF NOT (merged_props ? 'weight') THEN
                    merged_props := jsonb_set(merged_props, '{weight}', to_jsonb(0.0), TRUE);
                END IF;
                IF NOT (merged_props ? 'attributes') THEN
                    merged_props := jsonb_set(merged_props, '{attributes}', '{}'::jsonb, TRUE);
                END IF;
                IF NOT (merged_props ? 'mesh_elements') THEN
                    merged_props := jsonb_set(merged_props, '{mesh_elements}', to_jsonb(10), TRUE);
                END IF;

                UPDATE document_blocks
                SET
                    props = merged_props,
                    next_block_id = current_id
                WHERE block_id = heading.block_id;

                IF current_id IS NOT NULL THEN
                    UPDATE document_blocks
                    SET previous_block_id = heading.block_id
                    WHERE block_id = current_id
                      AND document_id = heading.document_id;
                END IF;

                IF array_length(delete_ids, 1) IS NOT NULL THEN
                    DELETE FROM document_blocks
                    WHERE block_id = ANY(delete_ids);
                END IF;
            END LOOP;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TEMP TABLE tmp_deformation_setup_merge ON COMMIT DROP AS
        SELECT
            leader.block_id AS leader_block_id,
            press.block_id AS press_block_id,
            die.block_id AS die_block_id,
            prolongation.block_id AS prolongation_block_id,
            upsetting.block_id AS upsetting_block_id,
            transversal.block_id AS transversal_block_id,
            transversal.next_block_id AS after_bundle_block_id,
            COALESCE(leader.props, '{}'::jsonb) AS leader_props,
            COALESCE(press.props, '{}'::jsonb) AS press_props,
            COALESCE(prolongation.props, '{}'::jsonb) AS prolongation_props,
            COALESCE(upsetting.props, '{}'::jsonb) AS upsetting_props,
            COALESCE(transversal.props, '{}'::jsonb) AS transversal_props
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
            props = (
                tmp.leader_props
                - 'title'
                - 'operation_type'
                - 'editable_fields'
                - 'field_limits'
            ) || jsonb_build_object(
                'press_id', COALESCE(tmp.press_props->'press_id', '1'::jsonb),
                'feed_direction_prolongation_id', COALESCE(tmp.prolongation_props->'feed_direction_prolongation_id', '3'::jsonb),
                'speed_prolongation', COALESCE(tmp.prolongation_props->'speed_prolongation', '""'::jsonb),
                'feed_direction_upsetting_id', COALESCE(tmp.upsetting_props->'feed_direction_upsetting_id', '3'::jsonb),
                'speed_upsetting', COALESCE(tmp.upsetting_props->'speed_upsetting', '""'::jsonb),
                'feed_direction_transversal_cogging_id', COALESCE(tmp.transversal_props->'feed_direction_transversal_cogging_id', '3'::jsonb),
                'speed_transversal_cogging', COALESCE(tmp.transversal_props->'speed_transversal_cogging', '""'::jsonb),
                'feed_first', COALESCE(tmp.prolongation_props->'feed_first', '""'::jsonb),
                'feed_middle', COALESCE(tmp.prolongation_props->'feed_middle', '""'::jsonb),
                'feed_last', COALESCE(tmp.prolongation_props->'feed_last', '""'::jsonb)
            ),
            next_block_id = tmp.after_bundle_block_id
        FROM tmp_deformation_setup_merge AS tmp
        WHERE leader.block_id = tmp.leader_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS after_bundle
        SET previous_block_id = tmp.leader_block_id
        FROM tmp_deformation_setup_merge AS tmp
        WHERE after_bundle.block_id = tmp.after_bundle_block_id
        """
    )
    op.execute(
        """
        DELETE FROM document_blocks AS old_block
        USING tmp_deformation_setup_merge AS tmp
        WHERE old_block.block_id IN (
            tmp.press_block_id,
            tmp.die_block_id,
            tmp.prolongation_block_id,
            tmp.upsetting_block_id,
            tmp.transversal_block_id
        )
        """
    )


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TEMP TABLE tmp_title_setup_restore ON COMMIT DROP AS
        SELECT
            heading.block_id AS heading_block_id,
            heading.document_id AS document_id,
            heading.next_block_id AS after_setup_block_id,
            COALESCE(heading.props, '{}'::jsonb) AS heading_props,
            heading.created_at AS created_at,
            heading.updated_at AS updated_at,
            gen_random_uuid() AS material_block_id,
            gen_random_uuid() AS input_workpiece_block_id,
            gen_random_uuid() AS mesh_block_id
        FROM document_blocks AS heading
        WHERE heading.block_type_id = 'document_heading'
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS heading
        SET
            props = tmp.heading_props
                - 'material_id'
                - 'geometry_type_id'
                - 'weight'
                - 'attributes'
                - 'mesh_elements',
            next_block_id = tmp.material_block_id
        FROM tmp_title_setup_restore AS tmp
        WHERE heading.block_id = tmp.heading_block_id
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
            material_block_id,
            document_id,
            heading_block_id,
            input_workpiece_block_id,
            '5',
            jsonb_build_object('material_id', COALESCE(heading_props->'material_id', '""'::jsonb)),
            created_at,
            updated_at,
            TRUE,
            FALSE,
            1
        FROM tmp_title_setup_restore
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
            input_workpiece_block_id,
            document_id,
            material_block_id,
            mesh_block_id,
            'input_workpiece',
            jsonb_build_object(
                'geometry_type_id', COALESCE(heading_props->'geometry_type_id', '""'::jsonb),
                'weight', COALESCE(heading_props->'weight', '0'::jsonb),
                'attributes', COALESCE(heading_props->'attributes', '{}'::jsonb)
            ),
            created_at,
            updated_at,
            TRUE,
            FALSE,
            2
        FROM tmp_title_setup_restore
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
            mesh_block_id,
            document_id,
            input_workpiece_block_id,
            after_setup_block_id,
            '84',
            jsonb_build_object('mesh_elements', COALESCE(heading_props->'mesh_elements', '10'::jsonb)),
            created_at,
            updated_at,
            TRUE,
            FALSE,
            3
        FROM tmp_title_setup_restore
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS after_setup
        SET previous_block_id = tmp.mesh_block_id
        FROM tmp_title_setup_restore AS tmp
        WHERE after_setup.block_id = tmp.after_setup_block_id
        """
    )

    op.execute(
        """
        CREATE TEMP TABLE tmp_deformation_setup_restore ON COMMIT DROP AS
        SELECT
            leader.block_id AS leader_block_id,
            leader.document_id AS document_id,
            leader.next_block_id AS after_bundle_block_id,
            COALESCE(leader.props, '{}'::jsonb) AS leader_props,
            leader.created_at AS created_at,
            leader.updated_at AS updated_at,
            gen_random_uuid() AS press_block_id,
            gen_random_uuid() AS die_block_id,
            gen_random_uuid() AS prolongation_block_id,
            gen_random_uuid() AS upsetting_block_id,
            gen_random_uuid() AS transversal_block_id
        FROM document_blocks AS leader
        LEFT JOIN document_blocks AS next_block
          ON next_block.block_id = leader.next_block_id
         AND next_block.document_id = leader.document_id
        WHERE leader.block_type_id = '24'
          AND COALESCE(next_block.block_type_id, '') <> '26'
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS leader
        SET
            props = '{}'::jsonb,
            next_block_id = tmp.press_block_id
        FROM tmp_deformation_setup_restore AS tmp
        WHERE leader.block_id = tmp.leader_block_id
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
            press_block_id,
            document_id,
            leader_block_id,
            die_block_id,
            '26',
            jsonb_build_object('press_id', COALESCE(leader_props->'press_id', '1'::jsonb)),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_setup_restore
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
            prolongation_block_id,
            '8',
            '{}'::jsonb,
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_setup_restore
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
            upsetting_block_id,
            '15',
            jsonb_build_object(
                'feed_direction_prolongation_id', COALESCE(leader_props->'feed_direction_prolongation_id', '3'::jsonb),
                'speed_prolongation', COALESCE(leader_props->'speed_prolongation', '""'::jsonb),
                'feed_first', COALESCE(leader_props->'feed_first', '""'::jsonb),
                'feed_middle', COALESCE(leader_props->'feed_middle', '""'::jsonb),
                'feed_last', COALESCE(leader_props->'feed_last', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_setup_restore
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
            transversal_block_id,
            '13',
            jsonb_build_object(
                'feed_direction_upsetting_id', COALESCE(leader_props->'feed_direction_upsetting_id', '3'::jsonb),
                'speed_upsetting', COALESCE(leader_props->'speed_upsetting', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_setup_restore
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
                'feed_direction_transversal_cogging_id', COALESCE(leader_props->'feed_direction_transversal_cogging_id', '3'::jsonb),
                'speed_transversal_cogging', COALESCE(leader_props->'speed_transversal_cogging', '""'::jsonb)
            ),
            created_at,
            updated_at,
            FALSE,
            TRUE,
            NULL
        FROM tmp_deformation_setup_restore
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS after_bundle
        SET previous_block_id = tmp.transversal_block_id
        FROM tmp_deformation_setup_restore AS tmp
        WHERE after_bundle.block_id = tmp.after_bundle_block_id
        """
    )

    op.execute(
        """
        UPDATE document_blocks_library
        SET
            auto_create_children = '26|8|15|13|14',
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
        SET is_obsolete = FALSE
        WHERE type_id IN (5, 84, 26, 8, 15, 13, 14)
        """
    )

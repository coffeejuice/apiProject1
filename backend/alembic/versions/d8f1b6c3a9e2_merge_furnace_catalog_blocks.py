"""merge furnace class and initial temperature block types

Revision ID: d8f1b6c3a9e2
Revises: c4a9d2e7b8f3
Create Date: 2026-04-21 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d8f1b6c3a9e2"
down_revision: Union[str, Sequence[str], None] = "c4a9d2e7b8f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Furnace',
            process_name = 'Furnace class: {}, temperature: {} °C',
            labels = 'Furnace class:|Temperature point [°C]:',
            db_column_names = 'furnace_class_id|temperature',
            trigger = 'accumulate',
            is_obsolete = FALSE
        WHERE type_id = 10
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = TRUE
        WHERE type_id = 62
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '23|23'
        WHERE type_id = 11
        """
    )

    op.execute(
        """
        WITH initial_temperatures AS (
            SELECT DISTINCT ON (document_id)
                document_id,
                props -> 'temperature' AS temperature
            FROM document_blocks
            WHERE block_type_id = '62'
              AND props ? 'temperature'
            ORDER BY document_id, created_at ASC
        )
        UPDATE document_blocks AS furnace
        SET props = COALESCE(furnace.props, '{}'::jsonb)
            || jsonb_build_object('temperature', initial_temperatures.temperature)
        FROM initial_temperatures
        WHERE furnace.document_id = initial_temperatures.document_id
          AND furnace.block_type_id = '10'
          AND initial_temperatures.temperature IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS previous_block
        SET next_block_id = obsolete_temperature.next_block_id
        FROM document_blocks AS obsolete_temperature
        WHERE obsolete_temperature.block_type_id = '62'
          AND previous_block.block_id = obsolete_temperature.previous_block_id
        """
    )
    op.execute(
        """
        UPDATE document_blocks AS next_block
        SET previous_block_id = obsolete_temperature.previous_block_id
        FROM document_blocks AS obsolete_temperature
        WHERE obsolete_temperature.block_type_id = '62'
          AND next_block.block_id = obsolete_temperature.next_block_id
        """
    )
    op.execute(
        """
        UPDATE documents AS document
        SET first_block_id = obsolete_temperature.next_block_id
        FROM document_blocks AS obsolete_temperature
        WHERE obsolete_temperature.block_type_id = '62'
          AND document.first_block_id = obsolete_temperature.block_id
        """
    )
    op.execute("DELETE FROM document_blocks WHERE block_type_id = '62'")


def downgrade() -> None:
    op.execute(
        """
        UPDATE document_blocks_library
        SET
            library_name = 'Furnace class',
            process_name = 'Furnace class: {}',
            labels = 'Furnace class:',
            db_column_names = 'furnace_class_id',
            trigger = 'accumulate',
            is_obsolete = FALSE
        WHERE type_id = 10
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET is_obsolete = FALSE
        WHERE type_id = 62
        """
    )
    op.execute(
        """
        UPDATE document_blocks_library
        SET auto_create_children = '62|23|23'
        WHERE type_id = 11
        """
    )
    op.execute(
        """
        UPDATE document_blocks
        SET props = props - 'temperature'
        WHERE block_type_id = '10'
        """
    )

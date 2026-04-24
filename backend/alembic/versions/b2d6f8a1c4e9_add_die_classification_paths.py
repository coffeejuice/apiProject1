"""add die classification paths

Revision ID: b2d6f8a1c4e9
Revises: a6e4c8f2b9d5
Create Date: 2026-04-22 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2d6f8a1c4e9"
down_revision: Union[str, Sequence[str], None] = "a6e4c8f2b9d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dies", sa.Column("classification_path", sa.String(length=255), nullable=True))
    op.add_column("die_assemblies", sa.Column("classification_path", sa.String(length=255), nullable=True))

    op.execute(
        """
        WITH linked_positions AS (
            SELECT top_die_id AS die_id, 'top' AS position
            FROM die_assemblies
            WHERE top_die_id IS NOT NULL
            UNION ALL
            SELECT bottom_die_id AS die_id, 'bottom' AS position
            FROM die_assemblies
            WHERE bottom_die_id IS NOT NULL
            UNION ALL
            SELECT left_die_id AS die_id, 'left' AS position
            FROM die_assemblies
            WHERE left_die_id IS NOT NULL
            UNION ALL
            SELECT right_die_id AS die_id, 'right' AS position
            FROM die_assemblies
            WHERE right_die_id IS NOT NULL
        ),
        preferred_positions AS (
            SELECT DISTINCT ON (die_id)
                die_id,
                position
            FROM linked_positions
            ORDER BY die_id,
                CASE position
                    WHEN 'top' THEN 1
                    WHEN 'bottom' THEN 2
                    WHEN 'left' THEN 3
                    WHEN 'right' THEN 4
                    ELSE 5
                END
        ),
        inferred_paths AS (
            SELECT
                dies.id,
                CASE
                    WHEN lower(die_types.name->>'EN') LIKE 'flat%' THEN 'flat'
                    WHEN lower(die_types.name->>'EN') LIKE 'v-%' THEN 'vdie'
                    WHEN lower(die_types.name->>'EN') LIKE 'gfm%' THEN 'gfm'
                    WHEN lower(die_types.name->>'EN') LIKE 'round%' THEN 'rounding'
                    WHEN lower(die_types.name->>'EN') LIKE 'knife%' THEN 'knife'
                    ELSE regexp_replace(lower(COALESCE(die_types.name->>'EN', 'unknown')), '[^a-z0-9]+', '_', 'g')
                END AS category,
                COALESCE(
                    preferred_positions.position,
                    CASE
                        WHEN lower(COALESCE(dies.die_template_file_name, '')) LIKE '%_top.%'
                            OR lower(COALESCE(dies.name->>'EN', '')) LIKE '%(top)%' THEN 'top'
                        WHEN lower(COALESCE(dies.die_template_file_name, '')) LIKE '%_bottom.%'
                            OR lower(COALESCE(dies.name->>'EN', '')) LIKE '%(bottom)%' THEN 'bottom'
                        WHEN lower(COALESCE(dies.die_template_file_name, '')) LIKE '%_plus_y.%'
                            OR lower(COALESCE(dies.name->>'EN', '')) LIKE '%(+y)%' THEN 'left'
                        WHEN lower(COALESCE(dies.die_template_file_name, '')) LIKE '%_minus_y.%'
                            OR lower(COALESCE(dies.name->>'EN', '')) LIKE '%(-y)%' THEN 'right'
                        ELSE NULL
                    END
                ) AS position
            FROM dies
            JOIN die_types ON die_types.id = dies.die_type_id
            LEFT JOIN preferred_positions ON preferred_positions.die_id = dies.id
        )
        UPDATE dies
        SET classification_path = inferred_paths.category ||
            CASE
                WHEN inferred_paths.position IS NULL THEN ''
                ELSE '.' || inferred_paths.position
            END
        FROM inferred_paths
        WHERE inferred_paths.id = dies.id
        """
    )

    op.execute(
        """
        WITH linked_categories AS (
            SELECT
                die_assemblies.id,
                split_part(
                    COALESCE(
                        left_die.classification_path,
                        right_die.classification_path,
                        top_die.classification_path,
                        bottom_die.classification_path,
                        'unknown'
                    ),
                    '.',
                    1
                ) AS category
            FROM die_assemblies
            LEFT JOIN dies AS top_die ON top_die.id = die_assemblies.top_die_id
            LEFT JOIN dies AS bottom_die ON bottom_die.id = die_assemblies.bottom_die_id
            LEFT JOIN dies AS left_die ON left_die.id = die_assemblies.left_die_id
            LEFT JOIN dies AS right_die ON right_die.id = die_assemblies.right_die_id
        )
        UPDATE die_assemblies
        SET classification_path = linked_categories.category || '.assembly'
        FROM linked_categories
        WHERE linked_categories.id = die_assemblies.id
        """
    )


def downgrade() -> None:
    op.drop_column("die_assemblies", "classification_path")
    op.drop_column("dies", "classification_path")

"""add material standards tables

Revision ID: c1f4e28b9a7d
Revises: 7f7f9945c6f1
Create Date: 2026-04-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c1f4e28b9a7d"
down_revision = "7f7f9945c6f1"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("material_standards_catalog"):
        op.create_table(
            "material_standards_catalog",
            sa.Column("standard_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("predecessor_standard_id", sa.Integer(), nullable=True),
            sa.Column("issue_organization", sa.String(length=127), nullable=True),
            sa.Column("issue_year", sa.Integer(), nullable=True),
            sa.Column(
                "geographic_level",
                sa.Enum(
                    "international",
                    "regional",
                    "national",
                    "private",
                    name="material_standard_geographic_level_enum",
                    native_enum=False,
                ),
                nullable=True,
            ),
            sa.Column("country_or_region", sa.String(length=63), nullable=True),
            sa.Column("title", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("standard_number", sa.String(length=255), nullable=False),
            sa.Column("url", sa.String(length=2047), nullable=True),
            sa.Column("file_name", sa.String(length=1023), nullable=True),
            sa.Column(
                "is_obsolete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["predecessor_standard_id"],
                ["material_standards_catalog.standard_id"],
                ondelete="SET NULL",
            ),
        )

    if not _table_exists("materials_designations"):
        op.create_table(
            "materials_designations",
            sa.Column("designation_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("designation", sa.String(length=255), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("standard_id", sa.Integer(), nullable=True),
            sa.Column(
                "is_main_designation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column(
                "is_obsolete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["material_id"],
                ["materials.material_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["standard_id"],
                ["material_standards_catalog.standard_id"],
                ondelete="SET NULL",
            ),
        )


def downgrade() -> None:
    if _table_exists("materials_designations"):
        op.drop_table("materials_designations")
    if _table_exists("material_standards_catalog"):
        op.drop_table("material_standards_catalog")

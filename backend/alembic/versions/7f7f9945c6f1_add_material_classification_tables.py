"""add material classification tables

Revision ID: 7f7f9945c6f1
Revises: 3a4d8f2c1b90
Create Date: 2026-04-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7f7f9945c6f1"
down_revision = "3a4d8f2c1b90"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("material_classification_axes"):
        op.create_table(
            "material_classification_axes",
            sa.Column("axis_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("key", sa.String(length=127), nullable=False),
            sa.Column("name", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("description", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "selection_mode",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'multi'"),
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "is_filter_visible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
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
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"],
                ["users.user_id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint("key", name="uq_material_classification_axes_key"),
        )

    if not _table_exists("material_classification_values"):
        op.create_table(
            "material_classification_values",
            sa.Column("value_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("axis_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=127), nullable=False),
            sa.Column("name", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("color", sa.String(length=63), nullable=True),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
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
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["axis_id"],
                ["material_classification_axes.axis_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"],
                ["users.user_id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint("axis_id", "key", name="uq_material_classification_values_axis_key"),
        )

    if not _table_exists("material_classification_assignments"):
        op.create_table(
            "material_classification_assignments",
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("value_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["material_id"],
                ["materials.material_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["value_id"],
                ["material_classification_values.value_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"],
                ["users.user_id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("material_id", "value_id"),
        )


def downgrade() -> None:
    if _table_exists("material_classification_assignments"):
        op.drop_table("material_classification_assignments")
    if _table_exists("material_classification_values"):
        op.drop_table("material_classification_values")
    if _table_exists("material_classification_axes"):
        op.drop_table("material_classification_axes")

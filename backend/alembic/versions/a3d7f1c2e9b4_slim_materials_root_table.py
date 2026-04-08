"""slim materials root table

Revision ID: a3d7f1c2e9b4
Revises: f7a2d4c8e1b3
Create Date: 2026-04-07 00:00:03.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a3d7f1c2e9b4"
down_revision = "f7a2d4c8e1b3"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _table_exists("materials"):
        return

    if _column_exists("materials", "file_name") and not _column_exists("materials", "deform_file_name"):
        op.alter_column("materials", "file_name", new_column_name="deform_file_name")

    if not _column_exists("materials", "note"):
        op.add_column("materials", sa.Column("note", sa.Text(), nullable=True))

    if _column_exists("materials", "deform_file_name"):
        op.execute("UPDATE materials SET deform_file_name = NULL WHERE NULLIF(BTRIM(deform_file_name), '') IS NULL")
        op.alter_column(
            "materials",
            "deform_file_name",
            existing_type=sa.String(length=1023),
            nullable=True,
            server_default=None,
        )

    for column_name in ("source", "source_version", "properties", "created_at", "obsolete_at"):
        if _column_exists("materials", column_name):
            op.drop_column("materials", column_name)


def downgrade() -> None:
    if not _table_exists("materials"):
        return

    if not _column_exists("materials", "source"):
        op.add_column(
            "materials",
            sa.Column(
                "source",
                sa.String(length=63),
                nullable=False,
                server_default=sa.text("''"),
            ),
        )
    if not _column_exists("materials", "source_version"):
        op.add_column(
            "materials",
            sa.Column(
                "source_version",
                sa.String(length=63),
                nullable=False,
                server_default=sa.text("''"),
            ),
        )
    if not _column_exists("materials", "properties"):
        op.add_column(
            "materials",
            sa.Column(
                "properties",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if not _column_exists("materials", "created_at"):
        op.add_column(
            "materials",
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    if not _column_exists("materials", "obsolete_at"):
        op.add_column(
            "materials",
            sa.Column("obsolete_at", sa.DateTime(), nullable=True),
        )

    if _column_exists("materials", "deform_file_name") and not _column_exists("materials", "file_name"):
        op.alter_column("materials", "deform_file_name", new_column_name="file_name")
        op.execute("UPDATE materials SET file_name = '' WHERE file_name IS NULL")
        op.alter_column(
            "materials",
            "file_name",
            existing_type=sa.String(length=1023),
            nullable=False,
            server_default=sa.text("''"),
        )

    if _column_exists("materials", "note"):
        op.drop_column("materials", "note")

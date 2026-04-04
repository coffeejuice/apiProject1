"""change press and die name columns to json

Revision ID: 444741afaf6d
Revises: 9132a4045788
Create Date: 2026-02-25 20:18:37.336079

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '444741afaf6d'
down_revision = '9132a4045788'
branch_labels = None
depends_on = None


TARGET_COLUMNS = (
    ("press", False),
    ("press_mode", True),
    ("die", False),
    ("die_assembly", False),
)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    for table_name, is_nullable in TARGET_COLUMNS:
        if not _table_exists(table_name):
            continue
        if not _column_exists(table_name, "name"):
            continue

        op.alter_column(
            table_name,
            "name",
            existing_type=sa.String(length=1023),
            type_=sa.JSON(),
            existing_nullable=is_nullable,
            postgresql_using="to_json(name::text)",
        )


def downgrade() -> None:
    for table_name, is_nullable in TARGET_COLUMNS:
        if not _table_exists(table_name):
            continue
        if not _column_exists(table_name, "name"):
            continue

        op.alter_column(
            table_name,
            "name",
            existing_type=sa.JSON(),
            type_=sa.String(length=1023),
            existing_nullable=is_nullable,
            postgresql_using=(
                "CASE "
                "WHEN name IS NULL THEN NULL "
                "WHEN json_typeof(name) = 'string' THEN trim(both '\"' from name::text) "
                "ELSE name::text "
                "END"
            ),
        )

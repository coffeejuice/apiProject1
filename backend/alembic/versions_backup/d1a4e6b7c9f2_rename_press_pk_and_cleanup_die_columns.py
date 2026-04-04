"""rename presses PK and cleanup dies/die_assemblies columns

Revision ID: d1a4e6b7c9f2
Revises: b8e4c1d2f6a7
Create Date: 2026-02-27 13:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a4e6b7c9f2"
down_revision = "b8e4c1d2f6a7"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _resolve_table(preferred: str, fallback: str | None = None) -> str | None:
    if _table_exists(preferred):
        return preferred
    if fallback and _table_exists(fallback):
        return fallback
    return None


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if _column_exists(table_name, new_name):
        return
    if not _column_exists(table_name, old_name):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};")


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _drop_server_default(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.alter_column(table_name, column_name, server_default=None)


def upgrade() -> None:
    presses_table = _resolve_table("presses", "press")
    dies_table = _resolve_table("dies", "die")
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")

    if presses_table:
        _rename_column_if_needed(presses_table, "press_id", "id")

    if dies_table:
        _rename_column_if_needed(dies_table, "dimensions", "properties")
        _drop_column_if_exists(dies_table, "updated_at")
        _drop_column_if_exists(dies_table, "is_matching_as_top")
        _drop_column_if_exists(dies_table, "is_matching_as_bottom")
        _drop_column_if_exists(dies_table, "is_matching_as_right")
        _drop_column_if_exists(dies_table, "is_matching_as_left")

    if die_assemblies_table:
        _drop_column_if_exists(die_assemblies_table, "updated_at")


def downgrade() -> None:
    presses_table = _resolve_table("presses", "press")
    dies_table = _resolve_table("dies", "die")
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")

    if presses_table:
        _rename_column_if_needed(presses_table, "id", "press_id")

    if dies_table:
        _rename_column_if_needed(dies_table, "properties", "dimensions")

        _add_column_if_missing(dies_table, sa.Column("updated_at", sa.DateTime(), nullable=True))

        _add_column_if_missing(
            dies_table,
            sa.Column("is_matching_as_top", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        _add_column_if_missing(
            dies_table,
            sa.Column("is_matching_as_bottom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        _add_column_if_missing(
            dies_table,
            sa.Column("is_matching_as_right", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        _add_column_if_missing(
            dies_table,
            sa.Column("is_matching_as_left", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

        _drop_server_default(dies_table, "is_matching_as_top")
        _drop_server_default(dies_table, "is_matching_as_bottom")
        _drop_server_default(dies_table, "is_matching_as_right")
        _drop_server_default(dies_table, "is_matching_as_left")

    if die_assemblies_table:
        _add_column_if_missing(die_assemblies_table, sa.Column("updated_at", sa.DateTime(), nullable=True))

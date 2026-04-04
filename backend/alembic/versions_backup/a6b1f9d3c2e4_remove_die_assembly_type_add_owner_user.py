"""remove die_assembly type and add owner_user_id columns

Revision ID: a6b1f9d3c2e4
Revises: e1d6a9f4c3b2
Create Date: 2026-02-27 08:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a6b1f9d3c2e4"
down_revision = "e1d6a9f4c3b2"
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


def _resolve_table(preferred: str, fallback: str) -> str | None:
    if _table_exists(preferred):
        return preferred
    if _table_exists(fallback):
        return fallback
    return None


def _fk_exists(table_name: str, column_name: str, referred_table: str, referred_column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (
            (fk.get("constrained_columns") or []) == [column_name]
            and fk.get("referred_table") == referred_table
            and (fk.get("referred_columns") or []) == [referred_column]
        ):
            return True
    return False


def _drop_fk_constraints_for_column(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (fk.get("constrained_columns") or []) == [column_name] and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def _add_owner_user_id(table_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, "owner_user_id"):
        op.add_column(table_name, sa.Column("owner_user_id", sa.Integer(), nullable=True))
    if _table_exists("users") and not _fk_exists(table_name, "owner_user_id", "users", "user_id"):
        op.create_foreign_key(
            f"fk_{table_name}_owner_user_id",
            table_name,
            "users",
            ["owner_user_id"],
            ["user_id"],
            ondelete="SET NULL",
        )


def _drop_owner_user_id(table_name: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, "owner_user_id"):
        _drop_fk_constraints_for_column(table_name, "owner_user_id")
        op.drop_column(table_name, "owner_user_id")


def upgrade() -> None:
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")
    dies_table = _resolve_table("dies", "die")
    presses_table = _resolve_table("presses", "press")
    press_modes_table = _resolve_table("press_modes", "press_mode")

    if die_assemblies_table and _column_exists(die_assemblies_table, "die_type_id"):
        _drop_fk_constraints_for_column(die_assemblies_table, "die_type_id")
        op.drop_column(die_assemblies_table, "die_type_id")

    for table_name in (die_assemblies_table, dies_table, presses_table, press_modes_table):
        if table_name:
            _add_owner_user_id(table_name)


def downgrade() -> None:
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")
    dies_table = _resolve_table("dies", "die")
    presses_table = _resolve_table("presses", "press")
    press_modes_table = _resolve_table("press_modes", "press_mode")
    die_types_table = _resolve_table("die_types", "die_type")

    for table_name in (die_assemblies_table, dies_table, presses_table, press_modes_table):
        if table_name:
            _drop_owner_user_id(table_name)

    if die_assemblies_table and not _column_exists(die_assemblies_table, "die_type_id"):
        op.add_column(die_assemblies_table, sa.Column("die_type_id", sa.Integer(), nullable=True))
    if (
        die_assemblies_table
        and die_types_table
        and _column_exists(die_assemblies_table, "die_type_id")
        and not _fk_exists(die_assemblies_table, "die_type_id", die_types_table, "id")
    ):
        op.create_foreign_key(
            f"fk_{die_assemblies_table}_die_type_id",
            die_assemblies_table,
            die_types_table,
            ["die_type_id"],
            ["id"],
            ondelete="RESTRICT",
        )

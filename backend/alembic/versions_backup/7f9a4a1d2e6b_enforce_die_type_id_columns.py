"""enforce die_type_id columns on die tables

Revision ID: 7f9a4a1d2e6b
Revises: c2b68f5f73af
Create Date: 2026-02-26 18:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f9a4a1d2e6b"
down_revision = "c2b68f5f73af"
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


def _drop_legacy_die_type_fks(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        constrained_columns = fk.get("constrained_columns") or []
        fk_name = fk.get("name")
        if constrained_columns == ["die_type"] and fk_name:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")


def _ensure_fk_on_die_type_id(table_name: str) -> None:
    if not _table_exists(table_name) or not _column_exists(table_name, "die_type_id"):
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_fk = any(
        (fk.get("constrained_columns") or []) == ["die_type_id"]
        and fk.get("referred_table") in {"die_types", "die_type"}
        for fk in inspector.get_foreign_keys(table_name)
    )
    if has_fk:
        return

    referred_table = None
    if _table_exists("die_types"):
        referred_table = "die_types"
    elif _table_exists("die_type"):
        referred_table = "die_type"
    if referred_table is None:
        return

    op.create_foreign_key(
        f"fk_{table_name}_die_type_id_enforced",
        table_name,
        referred_table,
        ["die_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _enforce_die_type_id_column(table_name: str) -> None:
    if not _table_exists(table_name):
        return

    has_old = _column_exists(table_name, "die_type")
    has_new = _column_exists(table_name, "die_type_id")

    if has_old and not has_new:
        op.execute(f"ALTER TABLE {table_name} RENAME COLUMN die_type TO die_type_id;")
        return

    if has_old and has_new:
        op.execute(
            f"UPDATE {table_name} "
            "SET die_type_id = COALESCE("
            "die_type_id, "
            "CASE die_type::text "
            "WHEN 'flat' THEN 1 "
            "WHEN 'v_die' THEN 2 "
            "WHEN 'gfm_die' THEN 3 "
            "WHEN 'rounding' THEN 4 "
            "WHEN 'knife' THEN 5 "
            "ELSE NULLIF(regexp_replace(die_type::text, '[^0-9-]', '', 'g'), '')::INTEGER "
            "END"
            ") "
            "WHERE die_type_id IS NULL;"
        )
        _drop_legacy_die_type_fks(table_name)
        op.execute(f"ALTER TABLE {table_name} DROP COLUMN die_type;")


def _rename_back_if_needed(table_name: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, "die_type"):
        return
    if not _column_exists(table_name, "die_type_id"):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN die_type_id TO die_type;")


def upgrade() -> None:
    for table_name in ("dies", "die_assemblies", "die", "die_assembly"):
        _enforce_die_type_id_column(table_name)
    for table_name in ("dies", "die_assemblies", "die", "die_assembly"):
        _ensure_fk_on_die_type_id(table_name)


def downgrade() -> None:
    for table_name in ("dies", "die_assemblies", "die", "die_assembly"):
        _rename_back_if_needed(table_name)

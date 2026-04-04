"""consolidate library schema updates

Revision ID: 4d7c4b8a9e21
Revises: 9b9c2f4e7c31
Create Date: 2026-02-26 20:15:00.000000

"""

import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d7c4b8a9e21"
down_revision = "9b9c2f4e7c31"
branch_labels = None
depends_on = None


TABLE_RENAMES = (
    ("press_mode", "press_modes"),
    ("press", "presses"),
    ("die", "dies"),
    ("die_assembly", "die_assemblies"),
    ("die_type", "die_types"),
    ("material", "materials"),
)

DIE_TYPE_ROWS = (
    (1, {"EN": "Flat die", "RU": "Плоский боёк", "ZH_HANS": "平砧"}),
    (2, {"EN": "V-die", "RU": "V-образный боёк", "ZH_HANS": "V形砧"}),
    (3, {"EN": "GFM die", "RU": "Боёк GFM", "ZH_HANS": "GFM砧"}),
    (4, {"EN": "Rounding die", "RU": "Радиусный боёк", "ZH_HANS": "圆角砧"}),
    (5, {"EN": "Knife die", "RU": "Ножевой боёк", "ZH_HANS": "刀形砧"}),
)


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _column_type_name(table_name: str, column_name: str) -> str | None:
    inspector = sa.inspect(op.get_bind())
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return str(col["type"]).lower()
    return None


def _fk_exists(table_name: str, constrained_columns: list[str], referred_table: str, referred_columns: list[str]) -> bool:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table_name):
        if (
            (fk.get("constrained_columns") or []) == constrained_columns
            and fk.get("referred_table") == referred_table
            and (fk.get("referred_columns") or []) == referred_columns
        ):
            return True
    return False


def _drop_fks_for_column(table_name: str, column_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table_name):
        if (fk.get("constrained_columns") or []) == [column_name] and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def _rename_table_if_needed(old_name: str, new_name: str) -> None:
    old_exists = _table_exists(old_name)
    new_exists = _table_exists(new_name)
    if old_exists and not new_exists:
        op.rename_table(old_name, new_name)


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, new_name):
        return
    if not _column_exists(table_name, old_name):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};")


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _table_exists(table_name) and _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, column.name):
        return
    op.add_column(table_name, column)


def _pluralize_tables() -> None:
    for old_name, new_name in TABLE_RENAMES:
        _rename_table_if_needed(old_name, new_name)


def _drop_furnace_class() -> None:
    if _table_exists("furnace_class"):
        op.execute("DROP TABLE furnace_class CASCADE;")


def _ensure_name_json(table_name: str) -> None:
    if not _table_exists(table_name) or not _column_exists(table_name, "name"):
        return
    type_name = _column_type_name(table_name, "name")
    if type_name and "json" in type_name:
        return
    op.execute(f"ALTER TABLE {table_name} ALTER COLUMN name TYPE JSON USING to_json(name::text);")


def _ensure_press_default_mode_fk() -> None:
    press_table = "presses" if _table_exists("presses") else ("press" if _table_exists("press") else None)
    press_mode_table = "press_modes" if _table_exists("press_modes") else ("press_mode" if _table_exists("press_mode") else None)
    if press_table is None:
        return

    _add_column_if_missing(press_table, sa.Column("default_press_mode_id", sa.Integer(), nullable=True))

    if press_mode_table and _column_exists(press_mode_table, "default_press_mode_id"):
        op.execute(
            f"""
            WITH defaults AS (
                SELECT press_id, MIN(default_press_mode_id) AS default_press_mode_id
                FROM {press_mode_table}
                WHERE default_press_mode_id IS NOT NULL
                  AND press_id IS NOT NULL
                GROUP BY press_id
            )
            UPDATE {press_table} AS p
            SET default_press_mode_id = defaults.default_press_mode_id
            FROM defaults
            WHERE p.press_id = defaults.press_id
              AND p.default_press_mode_id IS NULL;
            """
        )

    if press_mode_table and _column_exists(press_mode_table, "is_default_press_mode"):
        op.execute(
            f"""
            WITH defaults AS (
                SELECT press_id, MIN(press_mode_id) AS default_press_mode_id
                FROM {press_mode_table}
                WHERE is_default_press_mode IS TRUE
                  AND press_id IS NOT NULL
                GROUP BY press_id
            )
            UPDATE {press_table} AS p
            SET default_press_mode_id = defaults.default_press_mode_id
            FROM defaults
            WHERE p.press_id = defaults.press_id
              AND p.default_press_mode_id IS NULL;
            """
        )

    if press_mode_table and not _fk_exists(
        press_table,
        ["default_press_mode_id"],
        press_mode_table,
        ["press_mode_id"],
    ):
        op.create_foreign_key(
            "fk_press_default_press_mode_id",
            press_table,
            press_mode_table,
            ["default_press_mode_id"],
            ["press_mode_id"],
            ondelete="SET NULL",
        )


def _reshape_press_mode_columns() -> None:
    press_mode_table = "press_modes" if _table_exists("press_modes") else ("press_mode" if _table_exists("press_mode") else None)
    if press_mode_table is None:
        return

    _add_column_if_missing(
        press_mode_table,
        sa.Column("is_left_manipulator", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _add_column_if_missing(
        press_mode_table,
        sa.Column("is_right_manipulator", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    if _column_exists(press_mode_table, "manipulators_count"):
        op.execute(
            f"""
            UPDATE {press_mode_table}
            SET is_left_manipulator = COALESCE(manipulators_count, 0) >= 1,
                is_right_manipulator = COALESCE(manipulators_count, 0) >= 2;
            """
        )

    for legacy_col in (
        "press_mode_name",
        "press_die_match_code",
        "is_default_press_mode",
        "manipulators_count",
        "default_press_mode_id",
    ):
        _drop_column_if_exists(press_mode_table, legacy_col)


def _ensure_press_obsolete_columns() -> None:
    press_table = "presses" if _table_exists("presses") else ("press" if _table_exists("press") else None)
    if press_table is None:
        return

    _rename_column_if_needed(press_table, "is_obsolet", "is_obsolete")
    _add_column_if_missing(
        press_table,
        sa.Column("is_obsolete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _add_column_if_missing(
        press_table,
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    _add_column_if_missing(
        press_table,
        sa.Column("obsolete_at", sa.DateTime(), nullable=True),
    )


def _ensure_die_types_table() -> None:
    if _table_exists("die_type") and not _table_exists("die_types"):
        op.rename_table("die_type", "die_types")

    if not _table_exists("die_types"):
        op.create_table(
            "die_types",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.JSON(), nullable=False),
        )

    if _table_exists("die_type"):
        op.execute(
            """
            INSERT INTO die_types (id, name)
            SELECT id, name
            FROM die_type
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name;
            """
        )

    insert_stmt = sa.text(
        """
        INSERT INTO die_types (id, name)
        VALUES (:id, CAST(:name AS JSON))
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name
        """
    )
    for die_type_id, die_type_name in DIE_TYPE_ROWS:
        op.execute(
            insert_stmt.bindparams(
                id=die_type_id,
                name=json.dumps(die_type_name, ensure_ascii=False),
            )
        )

    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('die_types', 'id'),
            (SELECT COALESCE(MAX(id), 1) FROM die_types),
            TRUE
        );
        """
    )


def _ensure_die_type_id_column(table_name: str) -> None:
    if not _table_exists(table_name):
        return

    has_old = _column_exists(table_name, "die_type")
    has_new = _column_exists(table_name, "die_type_id")

    if has_old and not has_new:
        op.execute(f"ALTER TABLE {table_name} RENAME COLUMN die_type TO die_type_id;")
        has_old = False
        has_new = True

    if has_old and has_new:
        op.execute(
            f"""
            UPDATE {table_name}
            SET die_type_id = COALESCE(
                die_type_id,
                CASE die_type::text
                    WHEN 'flat' THEN 1
                    WHEN 'v_die' THEN 2
                    WHEN 'gfm_die' THEN 3
                    WHEN 'rounding' THEN 4
                    WHEN 'knife' THEN 5
                    WHEN '1' THEN 1
                    WHEN '2' THEN 2
                    WHEN '3' THEN 3
                    WHEN '4' THEN 4
                    WHEN '5' THEN 5
                    ELSE NULL
                END
            )
            WHERE die_type_id IS NULL;
            """
        )
        _drop_fks_for_column(table_name, "die_type")
        op.execute(f"ALTER TABLE {table_name} DROP COLUMN die_type;")

    if _column_exists(table_name, "die_type_id"):
        type_name = _column_type_name(table_name, "die_type_id")
        if type_name and "int" not in type_name:
            op.execute(
                f"""
                ALTER TABLE {table_name}
                ALTER COLUMN die_type_id TYPE INTEGER
                USING (
                    CASE die_type_id::text
                        WHEN 'flat' THEN 1
                        WHEN 'v_die' THEN 2
                        WHEN 'gfm_die' THEN 3
                        WHEN 'rounding' THEN 4
                        WHEN 'knife' THEN 5
                        WHEN '1' THEN 1
                        WHEN '2' THEN 2
                        WHEN '3' THEN 3
                        WHEN '4' THEN 4
                        WHEN '5' THEN 5
                        ELSE NULLIF(regexp_replace(die_type_id::text, '[^0-9-]', '', 'g'), '')::INTEGER
                    END
                );
                """
            )

        if _table_exists("die_types") and not _fk_exists(table_name, ["die_type_id"], "die_types", ["id"]):
            _drop_fks_for_column(table_name, "die_type_id")
            op.create_foreign_key(
                f"fk_{table_name}_die_type_id",
                table_name,
                "die_types",
                ["die_type_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def _ensure_map_tables() -> None:
    old_map = "die_assembly_die__map"
    new_map = "die_assembly_die_map"
    if _table_exists(old_map) and not _table_exists(new_map):
        op.rename_table(old_map, new_map)
    elif _table_exists(old_map) and _table_exists(new_map):
        op.execute(
            f"""
            INSERT INTO {new_map} (die_assembly_id, die_id)
            SELECT die_assembly_id, die_id
            FROM {old_map}
            ON CONFLICT (die_assembly_id, die_id) DO NOTHING;
            """
        )
        op.drop_table(old_map)

    press_table = "presses" if _table_exists("presses") else ("press" if _table_exists("press") else None)
    die_table = "dies" if _table_exists("dies") else ("die" if _table_exists("die") else None)
    die_assembly_table = "die_assemblies" if _table_exists("die_assemblies") else ("die_assembly" if _table_exists("die_assembly") else None)

    if press_table and die_table and not _table_exists("press_die_map"):
        op.create_table(
            "press_die_map",
            sa.Column("press_id", sa.Integer(), nullable=False),
            sa.Column("die_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["press_id"], [f"{press_table}.press_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["die_id"], [f"{die_table}.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("press_id", "die_id"),
        )

    if die_assembly_table and die_table and not _table_exists("die_assembly_die_map"):
        op.create_table(
            "die_assembly_die_map",
            sa.Column("die_assembly_id", sa.Integer(), nullable=False),
            sa.Column("die_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["die_assembly_id"], [f"{die_assembly_table}.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["die_id"], [f"{die_table}.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("die_assembly_id", "die_id"),
        )


def _drop_unused_die_type_enum() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'die_type_enum'
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_type t ON t.oid = a.atttypid
                WHERE t.typname = 'die_type_enum'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
            ) THEN
                DROP TYPE die_type_enum;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _pluralize_tables()
    _drop_furnace_class()

    for table_name in ("presses", "press_modes", "dies", "die_assemblies", "press", "press_mode", "die", "die_assembly"):
        _ensure_name_json(table_name)

    _ensure_press_default_mode_fk()
    _reshape_press_mode_columns()
    _ensure_press_obsolete_columns()

    for table_name in ("presses", "press"):
        _drop_column_if_exists(table_name, "press_die_match_code")

    _ensure_die_types_table()

    for table_name in ("dies", "die_assemblies", "die", "die_assembly"):
        _ensure_die_type_id_column(table_name)

    for table_name in ("dies", "die"):
        _drop_column_if_exists(table_name, "die_name")
        _drop_column_if_exists(table_name, "die_assembly_name")
        _drop_column_if_exists(table_name, "press_die_match_code")

    for table_name in ("die_assemblies", "die_assembly"):
        _drop_column_if_exists(table_name, "die_assembly_name")

    _ensure_map_tables()
    _drop_unused_die_type_enum()


def downgrade() -> None:
    # Consolidated migration keeps only forward path.
    return

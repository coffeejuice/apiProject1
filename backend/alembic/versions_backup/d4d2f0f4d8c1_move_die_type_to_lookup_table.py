"""move die_type to lookup table

Revision ID: d4d2f0f4d8c1
Revises: f3c87c8102a1
Create Date: 2026-02-26 10:55:00.000000

"""

import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4d2f0f4d8c1"
down_revision = "f3c87c8102a1"
branch_labels = None
depends_on = None


DIE_TYPE_ROWS = (
    (1, {"EN": "Flat die", "RU": "Плоский боёк", "ZH_HANS": "平砧"}),
    (2, {"EN": "V-die", "RU": "V-образный боёк", "ZH_HANS": "V形砧"}),
    (3, {"EN": "GFM die", "RU": "Боёк GFM", "ZH_HANS": "GFM砧"}),
    (4, {"EN": "Rounding die", "RU": "Радиусный боёк", "ZH_HANS": "圆角砧"}),
    (5, {"EN": "Knife die", "RU": "Ножевой боёк", "ZH_HANS": "刀形砧"}),
)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _column_type_name(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return str(col["type"]).lower()
    return None


def _has_die_type_fk(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (
            fk.get("referred_table") == "die_type"
            and fk.get("constrained_columns") == ["die_type"]
            and fk.get("referred_columns") == ["id"]
        ):
            return True
    return False


def _ensure_die_type_table() -> None:
    if not _table_exists("die_type"):
        op.create_table(
            "die_type",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.JSON(), nullable=False),
        )

    insert_stmt = sa.text(
        """
        INSERT INTO die_type (id, name)
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
            pg_get_serial_sequence('die_type', 'id'),
            (SELECT COALESCE(MAX(id), 1) FROM die_type),
            TRUE
        );
        """
    )


def _upgrade_die_type_column(table_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, "die_type"):
        return

    type_name = _column_type_name(table_name, "die_type")
    if type_name is None:
        return

    if "int" not in type_name:
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN die_type TYPE INTEGER
            USING (
                CASE die_type::text
                    WHEN 'flat' THEN 1
                    WHEN 'v_die' THEN 2
                    WHEN 'gfm_die' THEN 3
                    WHEN 'rounding' THEN 4
                    WHEN 'knife' THEN 5
                    ELSE 1
                END
            );
            """
        )

    if not _has_die_type_fk(table_name):
        op.create_foreign_key(
            f"fk_{table_name}_die_type_id",
            table_name,
            "die_type",
            ["die_type"],
            ["id"],
            ondelete="RESTRICT",
        )


def _drop_unused_enum_type() -> None:
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


def _drop_die_type_fk_constraints(table_name: str) -> None:
    if not _table_exists(table_name):
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints_to_drop: list[str] = []
    for fk in inspector.get_foreign_keys(table_name):
        if (
            fk.get("referred_table") == "die_type"
            and fk.get("constrained_columns") == ["die_type"]
            and fk.get("referred_columns") == ["id"]
        ):
            constraint_name = fk.get("name")
            if constraint_name:
                constraints_to_drop.append(constraint_name)

    for constraint_name in constraints_to_drop:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _downgrade_die_type_column(table_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, "die_type"):
        return

    type_name = _column_type_name(table_name, "die_type")
    if type_name is None or "int" not in type_name:
        return

    op.execute(
        f"""
        ALTER TABLE {table_name}
        ALTER COLUMN die_type TYPE die_type_enum
        USING (
            CASE die_type
                WHEN 1 THEN 'flat'
                WHEN 2 THEN 'v_die'
                WHEN 3 THEN 'gfm_die'
                WHEN 4 THEN 'rounding'
                WHEN 5 THEN 'knife'
                ELSE 'flat'
            END::die_type_enum
        );
        """
    )


def upgrade() -> None:
    _ensure_die_type_table()
    _upgrade_die_type_column("die_assembly")
    _upgrade_die_type_column("die")
    _drop_unused_enum_type()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'die_type_enum'
            ) THEN
                CREATE TYPE die_type_enum AS ENUM ('flat', 'v_die', 'rounding', 'knife', 'gfm_die');
            END IF;
        END $$;
        """
    )

    _drop_die_type_fk_constraints("die")
    _drop_die_type_fk_constraints("die_assembly")
    _downgrade_die_type_column("die")
    _downgrade_die_type_column("die_assembly")

    if _table_exists("die_type"):
        op.drop_table("die_type")

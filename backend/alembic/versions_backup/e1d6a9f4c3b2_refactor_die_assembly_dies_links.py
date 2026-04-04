"""refactor die_assembly/dies links and die fields

Revision ID: e1d6a9f4c3b2
Revises: 4d7c4b8a9e21
Create Date: 2026-02-26 21:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1d6a9f4c3b2"
down_revision = "4d7c4b8a9e21"
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


def _column_type_name(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return str(col["type"]).lower()
    return None


def _resolve_table(preferred: str, fallback: str) -> str | None:
    if _table_exists(preferred):
        return preferred
    if _table_exists(fallback):
        return fallback
    return None


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if not _table_exists(table_name):
        return
    if _column_exists(table_name, new_name):
        return
    if not _column_exists(table_name, old_name):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};")


def _drop_fk_constraints_for_column(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (fk.get("constrained_columns") or []) == [column_name] and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


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


def _add_die_assembly_slot_columns(die_assemblies_table: str, dies_table: str) -> None:
    slot_columns = ("top_die_id", "bottom_die_id", "left_die_id", "right_die_id")
    for col in slot_columns:
        if not _column_exists(die_assemblies_table, col):
            op.add_column(die_assemblies_table, sa.Column(col, sa.Integer(), nullable=True))
        if not _fk_exists(die_assemblies_table, col, dies_table, "id"):
            op.create_foreign_key(
                f"fk_{die_assemblies_table}_{col}",
                die_assemblies_table,
                dies_table,
                [col],
                ["id"],
                ondelete="SET NULL",
            )


def _safe_jsonb_cast_dimensions(dies_table: str) -> None:
    if not _column_exists(dies_table, "dimensions"):
        return

    type_name = _column_type_name(dies_table, "dimensions")
    if type_name and "jsonb" in type_name:
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION _forgelab_try_parse_jsonb(input_text TEXT)
        RETURNS JSONB
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF input_text IS NULL OR btrim(input_text) = '' THEN
                RETURN NULL;
            END IF;

            BEGIN
                RETURN input_text::jsonb;
            EXCEPTION
                WHEN others THEN
                    RETURN to_jsonb(input_text);
            END;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        ALTER TABLE {dies_table}
        ALTER COLUMN dimensions TYPE JSONB
        USING _forgelab_try_parse_jsonb(dimensions);
        """
    )
    op.execute("DROP FUNCTION IF EXISTS _forgelab_try_parse_jsonb(TEXT);")


def upgrade() -> None:
    dies_table = _resolve_table("dies", "die")
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")

    if dies_table and die_assemblies_table:
        _add_die_assembly_slot_columns(die_assemblies_table, dies_table)

        # Backfill die slots from existing dies associations if present.
        if _column_exists(dies_table, "die_assembly_id"):
            right_match_col = (
                "is_matching_as_right"
                if _column_exists(dies_table, "is_matching_as_right")
                else ("is_matching_as_minus_y" if _column_exists(dies_table, "is_matching_as_minus_y") else None)
            )
            left_match_col = (
                "is_matching_as_left"
                if _column_exists(dies_table, "is_matching_as_left")
                else ("is_matching_as_plus_y" if _column_exists(dies_table, "is_matching_as_plus_y") else None)
            )
            right_expr = f"COALESCE(d.{right_match_col}, FALSE)" if right_match_col else "FALSE"
            left_expr = f"COALESCE(d.{left_match_col}, FALSE)" if left_match_col else "FALSE"

            op.execute(
                f"""
                WITH links AS (
                    SELECT
                        d.die_assembly_id,
                        MIN(CASE WHEN COALESCE(d.is_matching_as_top, FALSE) THEN d.id END) AS top_die_id,
                        MIN(CASE WHEN COALESCE(d.is_matching_as_bottom, FALSE) THEN d.id END) AS bottom_die_id,
                        MIN(CASE WHEN {left_expr} THEN d.id END) AS left_die_id,
                        MIN(CASE WHEN {right_expr} THEN d.id END) AS right_die_id
                    FROM {dies_table} d
                    WHERE d.die_assembly_id IS NOT NULL
                    GROUP BY d.die_assembly_id
                )
                UPDATE {die_assemblies_table} da
                SET
                    top_die_id = COALESCE(da.top_die_id, links.top_die_id),
                    bottom_die_id = COALESCE(da.bottom_die_id, links.bottom_die_id),
                    left_die_id = COALESCE(da.left_die_id, links.left_die_id),
                    right_die_id = COALESCE(da.right_die_id, links.right_die_id)
                FROM links
                WHERE da.id = links.die_assembly_id;
                """
            )

    if dies_table:
        _rename_column_if_needed(dies_table, "is_matching_as_minus_y", "is_matching_as_right")
        _rename_column_if_needed(dies_table, "is_matching_as_plus_y", "is_matching_as_left")
        _safe_jsonb_cast_dimensions(dies_table)

        if _column_exists(dies_table, "die_assembly_id"):
            _drop_fk_constraints_for_column(dies_table, "die_assembly_id")
            op.drop_column(dies_table, "die_assembly_id")

    # Legacy map table is no longer needed.
    if _table_exists("die_assembly_die_map"):
        op.drop_table("die_assembly_die_map")
    if _table_exists("die_assembly_die__map"):
        op.drop_table("die_assembly_die__map")


def downgrade() -> None:
    dies_table = _resolve_table("dies", "die")
    die_assemblies_table = _resolve_table("die_assemblies", "die_assembly")

    if dies_table and die_assemblies_table and not _table_exists("die_assembly_die_map"):
        op.create_table(
            "die_assembly_die_map",
            sa.Column("die_assembly_id", sa.Integer(), nullable=False),
            sa.Column("die_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["die_assembly_id"], [f"{die_assemblies_table}.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["die_id"], [f"{dies_table}.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("die_assembly_id", "die_id"),
        )

    if dies_table and die_assemblies_table:
        if not _column_exists(dies_table, "die_assembly_id"):
            op.add_column(dies_table, sa.Column("die_assembly_id", sa.Integer(), nullable=True))
        if not _fk_exists(dies_table, "die_assembly_id", die_assemblies_table, "id"):
            op.create_foreign_key(
                f"fk_{dies_table}_die_assembly_id",
                dies_table,
                die_assemblies_table,
                ["die_assembly_id"],
                ["id"],
                ondelete="RESTRICT",
            )

        if all(_column_exists(die_assemblies_table, c) for c in ("top_die_id", "bottom_die_id", "left_die_id", "right_die_id")):
            op.execute(
                f"""
                WITH links AS (
                    SELECT id AS die_assembly_id, top_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE top_die_id IS NOT NULL
                    UNION ALL
                    SELECT id AS die_assembly_id, bottom_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE bottom_die_id IS NOT NULL
                    UNION ALL
                    SELECT id AS die_assembly_id, left_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE left_die_id IS NOT NULL
                    UNION ALL
                    SELECT id AS die_assembly_id, right_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE right_die_id IS NOT NULL
                )
                UPDATE {dies_table} d
                SET die_assembly_id = links.die_assembly_id
                FROM links
                WHERE d.id = links.die_id
                  AND d.die_assembly_id IS NULL;
                """
            )
            if _table_exists("die_assembly_die_map"):
                op.execute(
                    f"""
                    INSERT INTO die_assembly_die_map (die_assembly_id, die_id)
                    SELECT id AS die_assembly_id, top_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE top_die_id IS NOT NULL
                    UNION
                    SELECT id AS die_assembly_id, bottom_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE bottom_die_id IS NOT NULL
                    UNION
                    SELECT id AS die_assembly_id, left_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE left_die_id IS NOT NULL
                    UNION
                    SELECT id AS die_assembly_id, right_die_id AS die_id
                    FROM {die_assemblies_table}
                    WHERE right_die_id IS NOT NULL
                    ON CONFLICT (die_assembly_id, die_id) DO NOTHING;
                    """
                )

    if dies_table:
        _rename_column_if_needed(dies_table, "is_matching_as_right", "is_matching_as_minus_y")
        _rename_column_if_needed(dies_table, "is_matching_as_left", "is_matching_as_plus_y")

        if _column_exists(dies_table, "dimensions"):
            type_name = _column_type_name(dies_table, "dimensions")
            if type_name and "jsonb" in type_name:
                op.execute(
                    f"""
                    ALTER TABLE {dies_table}
                    ALTER COLUMN dimensions TYPE VARCHAR(4095)
                    USING (
                        CASE
                            WHEN dimensions IS NULL THEN NULL
                            WHEN jsonb_typeof(dimensions) = 'string' THEN trim(both '"' from dimensions::text)
                            ELSE dimensions::text
                        END
                    );
                    """
                )

    if die_assemblies_table:
        for col in ("top_die_id", "bottom_die_id", "left_die_id", "right_die_id"):
            if _column_exists(die_assemblies_table, col):
                _drop_fk_constraints_for_column(die_assemblies_table, col)
                op.drop_column(die_assemblies_table, col)

"""refactor press_modes structure with properties JSONB and id column

Revision ID: b8e4c1d2f6a7
Revises: c5d9e2a71b3f
Create Date: 2026-02-27 12:20:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b8e4c1d2f6a7"
down_revision = "c5d9e2a71b3f"
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


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if _column_exists(table_name, new_name):
        return
    if not _column_exists(table_name, old_name):
        return
    op.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};")


def upgrade() -> None:
    press_modes_table = _resolve_table("press_modes", "press_mode")
    if not press_modes_table:
        return

    _add_column_if_missing(
        press_modes_table,
        sa.Column("is_obsolete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _add_column_if_missing(
        press_modes_table,
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    _add_column_if_missing(
        press_modes_table,
        sa.Column("obsolete_at", sa.DateTime(), nullable=True),
    )
    _add_column_if_missing(
        press_modes_table,
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    source_columns = (
        "automatic_feed_mode_is_on_when_bites_count",
        "max_force",
        "back_speed",
        "idle_speed",
        "working_speed",
        "min_dwell_speed",
        "max_dwell_time",
        "min_idle_stroke",
        "max_idle_stroke",
        "approaching_distance",
        "open_height_without_dies",
        "power_limit",
        "is_left_manipulator",
        "is_right_manipulator",
    )
    if all(_column_exists(press_modes_table, col) for col in source_columns):
        op.execute(
            f"""
            UPDATE {press_modes_table}
            SET properties = COALESCE(properties, '{{}}'::jsonb) || jsonb_build_object(
                'automatic_feed_mode_is_on_when_bites_count', automatic_feed_mode_is_on_when_bites_count,
                'max_force', max_force,
                'back_speed', back_speed,
                'idle_speed', idle_speed,
                'working_speed', working_speed,
                'min_dwell_speed', min_dwell_speed,
                'max_dwell_time', max_dwell_time,
                'min_idle_stroke', min_idle_stroke,
                'max_idle_stroke', max_idle_stroke,
                'approaching_distance', approaching_distance,
                'open_height_without_dies', open_height_without_dies,
                'power_limit', power_limit,
                'is_left_manipulator', is_left_manipulator,
                'is_right_manipulator', is_right_manipulator
            );
            """
        )

    for col in source_columns:
        _drop_column_if_exists(press_modes_table, col)

    _rename_column_if_needed(press_modes_table, "press_mode_id", "id")


def downgrade() -> None:
    press_modes_table = _resolve_table("press_modes", "press_mode")
    if not press_modes_table:
        return

    source_columns = (
        ("automatic_feed_mode_is_on_when_bites_count", sa.SmallInteger(), True, None),
        ("max_force", sa.Float(), True, None),
        ("back_speed", sa.Float(), True, None),
        ("idle_speed", sa.Float(), True, None),
        ("working_speed", sa.Float(), True, None),
        ("min_dwell_speed", sa.Float(), True, None),
        ("max_dwell_time", sa.Float(), True, None),
        ("min_idle_stroke", sa.Float(), True, None),
        ("max_idle_stroke", sa.Float(), True, None),
        ("approaching_distance", sa.Float(), True, None),
        ("open_height_without_dies", sa.Float(), True, None),
        ("power_limit", postgresql.JSONB(), True, None),
        ("is_left_manipulator", sa.Boolean(), False, sa.text("false")),
        ("is_right_manipulator", sa.Boolean(), False, sa.text("false")),
    )

    for name, col_type, nullable, default in source_columns:
        _add_column_if_missing(
            press_modes_table,
            sa.Column(name, col_type, nullable=nullable, server_default=default),
        )

    if _column_exists(press_modes_table, "properties"):
        op.execute(
            f"""
            UPDATE {press_modes_table}
            SET
                automatic_feed_mode_is_on_when_bites_count = CASE
                    WHEN properties ? 'automatic_feed_mode_is_on_when_bites_count'
                    THEN NULLIF(properties->>'automatic_feed_mode_is_on_when_bites_count', '')::smallint
                    ELSE automatic_feed_mode_is_on_when_bites_count
                END,
                max_force = CASE
                    WHEN properties ? 'max_force'
                    THEN NULLIF(properties->>'max_force', '')::double precision
                    ELSE max_force
                END,
                back_speed = CASE
                    WHEN properties ? 'back_speed'
                    THEN NULLIF(properties->>'back_speed', '')::double precision
                    ELSE back_speed
                END,
                idle_speed = CASE
                    WHEN properties ? 'idle_speed'
                    THEN NULLIF(properties->>'idle_speed', '')::double precision
                    ELSE idle_speed
                END,
                working_speed = CASE
                    WHEN properties ? 'working_speed'
                    THEN NULLIF(properties->>'working_speed', '')::double precision
                    ELSE working_speed
                END,
                min_dwell_speed = CASE
                    WHEN properties ? 'min_dwell_speed'
                    THEN NULLIF(properties->>'min_dwell_speed', '')::double precision
                    ELSE min_dwell_speed
                END,
                max_dwell_time = CASE
                    WHEN properties ? 'max_dwell_time'
                    THEN NULLIF(properties->>'max_dwell_time', '')::double precision
                    ELSE max_dwell_time
                END,
                min_idle_stroke = CASE
                    WHEN properties ? 'min_idle_stroke'
                    THEN NULLIF(properties->>'min_idle_stroke', '')::double precision
                    ELSE min_idle_stroke
                END,
                max_idle_stroke = CASE
                    WHEN properties ? 'max_idle_stroke'
                    THEN NULLIF(properties->>'max_idle_stroke', '')::double precision
                    ELSE max_idle_stroke
                END,
                approaching_distance = CASE
                    WHEN properties ? 'approaching_distance'
                    THEN NULLIF(properties->>'approaching_distance', '')::double precision
                    ELSE approaching_distance
                END,
                open_height_without_dies = CASE
                    WHEN properties ? 'open_height_without_dies'
                    THEN NULLIF(properties->>'open_height_without_dies', '')::double precision
                    ELSE open_height_without_dies
                END,
                power_limit = CASE
                    WHEN properties ? 'power_limit'
                    THEN properties->'power_limit'
                    ELSE power_limit
                END,
                is_left_manipulator = CASE
                    WHEN properties ? 'is_left_manipulator'
                    THEN COALESCE((properties->>'is_left_manipulator')::boolean, false)
                    ELSE is_left_manipulator
                END,
                is_right_manipulator = CASE
                    WHEN properties ? 'is_right_manipulator'
                    THEN COALESCE((properties->>'is_right_manipulator')::boolean, false)
                    ELSE is_right_manipulator
                END;
            """
        )

    _drop_column_if_exists(press_modes_table, "properties")
    _drop_column_if_exists(press_modes_table, "is_obsolete")
    _drop_column_if_exists(press_modes_table, "created_at")
    _drop_column_if_exists(press_modes_table, "obsolete_at")

    _rename_column_if_needed(press_modes_table, "id", "press_mode_id")

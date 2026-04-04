"""move default press mode marker from presses to press_modes

Revision ID: a7d2c9e4b1f6
Revises: f4c1e9a2b7d6
Create Date: 2026-02-27 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7d2c9e4b1f6"
down_revision = "f4c1e9a2b7d6"
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


def upgrade() -> None:
    presses_table = _resolve_table("presses", "press")
    press_modes_table = _resolve_table("press_modes", "press_mode")
    if not press_modes_table:
        return

    if not _column_exists(press_modes_table, "default_press_mode"):
        op.add_column(
            press_modes_table,
            sa.Column("default_press_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if presses_table and _column_exists(presses_table, "default_press_mode_id"):
        op.execute(
            f"""
            UPDATE {press_modes_table} pm
            SET default_press_mode = TRUE
            FROM {presses_table} p
            WHERE p.default_press_mode_id IS NOT NULL
              AND pm.id = p.default_press_mode_id;
            """
        )

        _drop_fk_constraints_for_column(presses_table, "default_press_mode_id")
        op.drop_column(presses_table, "default_press_mode_id")


def downgrade() -> None:
    presses_table = _resolve_table("presses", "press")
    press_modes_table = _resolve_table("press_modes", "press_mode")
    if not press_modes_table or not presses_table:
        return

    if not _column_exists(presses_table, "default_press_mode_id"):
        op.add_column(presses_table, sa.Column("default_press_mode_id", sa.Integer(), nullable=True))

    op.execute(
        f"""
        WITH defaults AS (
            SELECT press_id, MIN(id) AS default_press_mode_id
            FROM {press_modes_table}
            WHERE default_press_mode IS TRUE
              AND press_id IS NOT NULL
            GROUP BY press_id
        )
        UPDATE {presses_table} p
        SET default_press_mode_id = defaults.default_press_mode_id
        FROM defaults
        WHERE p.id = defaults.press_id;
        """
    )

    if not _fk_exists(presses_table, "default_press_mode_id", press_modes_table, "id"):
        op.create_foreign_key(
            "fk_press_default_press_mode_id",
            presses_table,
            press_modes_table,
            ["default_press_mode_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if _column_exists(press_modes_table, "default_press_mode"):
        op.drop_column(press_modes_table, "default_press_mode")

"""Require strict simulation step to document operation links.

Revision ID: 0003_strict_step_doc_op
Revises: 0002_doc_op_params
Create Date: 2026-05-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_strict_step_doc_op"
down_revision: Union[str, Sequence[str], None] = "0002_doc_op_params"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "simulation_steps"
COLUMN_NAME = "document_operation_id"
STRICT_FK_NAME = "fk_simulation_steps_document_operation_id"
STRICT_UNIQUE_NAME = "uq_simulation_steps_document_operation"


def _constraint_names(kind: str, *, constrained_column: str | None = None) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if kind == "fk":
        constraints = inspector.get_foreign_keys(TABLE_NAME)
        return {
            str(constraint["name"])
            for constraint in constraints
            if constraint.get("name")
            and (
                constrained_column is None
                or constrained_column in constraint.get("constrained_columns", [])
            )
        }
    if kind == "unique":
        constraints = inspector.get_unique_constraints(TABLE_NAME)
        return {
            str(constraint["name"])
            for constraint in constraints
            if constraint.get("name")
            and (
                constrained_column is None
                or constrained_column in constraint.get("column_names", [])
            )
        }
    return set()


def _column_is_nullable() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for column in inspector.get_columns(TABLE_NAME):
        if column["name"] == COLUMN_NAME:
            return bool(column.get("nullable", True))
    return False


def upgrade() -> None:
    # Legacy rows without a document operation cannot satisfy the strict link.
    op.execute(
        sa.text(
            """
            DELETE FROM simulation_steps
            WHERE document_operation_id IS NULL
            """
        )
    )

    for name in _constraint_names("fk", constrained_column=COLUMN_NAME):
        op.drop_constraint(name, TABLE_NAME, type_="foreignkey")

    if _column_is_nullable():
        op.alter_column(
            TABLE_NAME,
            COLUMN_NAME,
            existing_type=sa.BigInteger(),
            nullable=False,
        )

    op.create_foreign_key(
        STRICT_FK_NAME,
        TABLE_NAME,
        "document_operations",
        [COLUMN_NAME],
        ["document_operation_id"],
        ondelete="RESTRICT",
    )

    existing_unique_names = _constraint_names("unique", constrained_column=COLUMN_NAME)
    if not existing_unique_names:
        op.create_unique_constraint(STRICT_UNIQUE_NAME, TABLE_NAME, [COLUMN_NAME])


def downgrade() -> None:
    for name in _constraint_names("unique", constrained_column=COLUMN_NAME):
        if name == STRICT_UNIQUE_NAME:
            op.drop_constraint(name, TABLE_NAME, type_="unique")

    for name in _constraint_names("fk", constrained_column=COLUMN_NAME):
        op.drop_constraint(name, TABLE_NAME, type_="foreignkey")

    op.alter_column(
        TABLE_NAME,
        COLUMN_NAME,
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    op.create_foreign_key(
        "simulation_steps_document_operation_id_fkey",
        TABLE_NAME,
        "document_operations",
        [COLUMN_NAME],
        ["document_operation_id"],
        ondelete="SET NULL",
    )

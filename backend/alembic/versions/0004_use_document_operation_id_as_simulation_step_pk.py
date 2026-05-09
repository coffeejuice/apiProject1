"""Use document_operation_id as simulation step identity.

Revision ID: 0004_doc_op_step_pk
Revises: 0003_strict_step_doc_op
Create Date: 2026-05-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_doc_op_step_pk"
down_revision: Union[str, Sequence[str], None] = "0003_strict_step_doc_op"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SIMULATION_STEPS = "simulation_steps"
SIMULATION_STEP_STATUS = "simulation_step_status"
POSTPROCESSING_TASKS = "postprocessing_tasks"
OLD_ID = "simulation_step_id"
NEW_ID = "document_operation_id"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {str(column["name"]) for column in _inspector().get_columns(table_name)}


def _column_is_nullable(table_name: str, column_name: str) -> bool:
    for column in _inspector().get_columns(table_name):
        if column["name"] == column_name:
            return bool(column.get("nullable", True))
    return False


def _pk_name(table_name: str) -> str | None:
    pk = _inspector().get_pk_constraint(table_name)
    name = pk.get("name")
    return str(name) if name else None


def _pk_columns(table_name: str) -> list[str]:
    pk = _inspector().get_pk_constraint(table_name)
    return [str(column) for column in pk.get("constrained_columns", [])]


def _fk_names(table_name: str, *, constrained_column: str | None = None) -> set[str]:
    if not _table_exists(table_name):
        return set()
    names: set[str] = set()
    for constraint in _inspector().get_foreign_keys(table_name):
        name = constraint.get("name")
        columns = [str(column) for column in constraint.get("constrained_columns", [])]
        if name and (constrained_column is None or constrained_column in columns):
            names.add(str(name))
    return names


def _unique_names(table_name: str, *, constrained_column: str | None = None) -> set[str]:
    if not _table_exists(table_name):
        return set()
    names: set[str] = set()
    for constraint in _inspector().get_unique_constraints(table_name):
        name = constraint.get("name")
        columns = [str(column) for column in constraint.get("column_names", [])]
        if name and (constrained_column is None or constrained_column in columns):
            names.add(str(name))
    return names


def _index_names(table_name: str, *, column_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    names: set[str] = set()
    for index in _inspector().get_indexes(table_name):
        name = index.get("name")
        columns = [str(column) for column in index.get("column_names", [])]
        if name and column_name in columns:
            names.add(str(name))
    return names


def _drop_foreign_keys(table_name: str, column_name: str) -> None:
    for name in _fk_names(table_name, constrained_column=column_name):
        op.drop_constraint(name, table_name, type_="foreignkey")


def _drop_unique_constraints(table_name: str, column_name: str) -> None:
    for name in _unique_names(table_name, constrained_column=column_name):
        op.drop_constraint(name, table_name, type_="unique")


def _drop_indexes(table_name: str, column_name: str) -> None:
    for name in _index_names(table_name, column_name=column_name):
        op.drop_index(name, table_name=table_name)


def _ensure_column_not_null(table_name: str, column_name: str) -> None:
    if _column_is_nullable(table_name, column_name):
        op.alter_column(table_name, column_name, existing_type=sa.BigInteger(), nullable=False)


def _create_fk_if_missing(table_name: str, name: str) -> None:
    if _fk_names(table_name, constrained_column=NEW_ID):
        return
    op.create_foreign_key(
        name,
        table_name,
        SIMULATION_STEPS,
        [NEW_ID],
        [NEW_ID],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    if not _table_exists(SIMULATION_STEPS):
        return

    status_columns = _column_names(SIMULATION_STEP_STATUS)
    if OLD_ID in status_columns and NEW_ID not in status_columns:
        op.add_column(SIMULATION_STEP_STATUS, sa.Column(NEW_ID, sa.BigInteger(), nullable=True))
        status_columns.add(NEW_ID)
    if OLD_ID in status_columns and NEW_ID in status_columns:
        op.execute(
            sa.text(
                """
                UPDATE simulation_step_status AS status
                SET document_operation_id = step.document_operation_id
                FROM simulation_steps AS step
                WHERE status.simulation_step_id = step.simulation_step_id
                  AND status.document_operation_id IS NULL
                """
            )
        )
        op.execute(sa.text("DELETE FROM simulation_step_status WHERE document_operation_id IS NULL"))
        _ensure_column_not_null(SIMULATION_STEP_STATUS, NEW_ID)

    post_columns = _column_names(POSTPROCESSING_TASKS)
    if OLD_ID in post_columns and NEW_ID not in post_columns:
        op.add_column(POSTPROCESSING_TASKS, sa.Column(NEW_ID, sa.BigInteger(), nullable=True))
        post_columns.add(NEW_ID)
    if OLD_ID in post_columns and NEW_ID in post_columns:
        op.execute(
            sa.text(
                """
                UPDATE postprocessing_tasks AS task
                SET document_operation_id = step.document_operation_id
                FROM simulation_steps AS step
                WHERE task.simulation_step_id = step.simulation_step_id
                  AND task.document_operation_id IS NULL
                """
            )
        )
        op.execute(sa.text("DELETE FROM postprocessing_tasks WHERE document_operation_id IS NULL"))
        _ensure_column_not_null(POSTPROCESSING_TASKS, NEW_ID)

    if OLD_ID in _column_names(SIMULATION_STEP_STATUS):
        _drop_foreign_keys(SIMULATION_STEP_STATUS, OLD_ID)
        if OLD_ID in _pk_columns(SIMULATION_STEP_STATUS):
            pk_name = _pk_name(SIMULATION_STEP_STATUS)
            if pk_name:
                op.drop_constraint(pk_name, SIMULATION_STEP_STATUS, type_="primary")
        _drop_indexes(SIMULATION_STEP_STATUS, OLD_ID)
        op.drop_column(SIMULATION_STEP_STATUS, OLD_ID)

    if OLD_ID in _column_names(POSTPROCESSING_TASKS):
        _drop_foreign_keys(POSTPROCESSING_TASKS, OLD_ID)
        _drop_unique_constraints(POSTPROCESSING_TASKS, OLD_ID)
        _drop_indexes(POSTPROCESSING_TASKS, OLD_ID)
        op.drop_column(POSTPROCESSING_TASKS, OLD_ID)

    if NEW_ID in _column_names(SIMULATION_STEPS):
        _ensure_column_not_null(SIMULATION_STEPS, NEW_ID)
        _drop_unique_constraints(SIMULATION_STEPS, NEW_ID)
        _drop_indexes(SIMULATION_STEPS, NEW_ID)

    if OLD_ID in _column_names(SIMULATION_STEPS):
        if OLD_ID in _pk_columns(SIMULATION_STEPS):
            pk_name = _pk_name(SIMULATION_STEPS)
            if pk_name:
                op.drop_constraint(pk_name, SIMULATION_STEPS, type_="primary")
        _drop_indexes(SIMULATION_STEPS, OLD_ID)
        op.drop_column(SIMULATION_STEPS, OLD_ID)

    if _pk_columns(SIMULATION_STEPS) != [NEW_ID]:
        pk_name = _pk_name(SIMULATION_STEPS)
        if pk_name:
            op.drop_constraint(pk_name, SIMULATION_STEPS, type_="primary")
        op.create_primary_key("pk_simulation_steps_document_operation_id", SIMULATION_STEPS, [NEW_ID])

    if _table_exists(SIMULATION_STEP_STATUS) and NEW_ID in _column_names(SIMULATION_STEP_STATUS):
        if _pk_columns(SIMULATION_STEP_STATUS) != [NEW_ID]:
            pk_name = _pk_name(SIMULATION_STEP_STATUS)
            if pk_name:
                op.drop_constraint(pk_name, SIMULATION_STEP_STATUS, type_="primary")
            op.create_primary_key("pk_simulation_step_status_document_operation_id", SIMULATION_STEP_STATUS, [NEW_ID])
        _create_fk_if_missing(
            SIMULATION_STEP_STATUS,
            "fk_simulation_step_status_document_operation_id",
        )

    if _table_exists(POSTPROCESSING_TASKS) and NEW_ID in _column_names(POSTPROCESSING_TASKS):
        _create_fk_if_missing(
            POSTPROCESSING_TASKS,
            "fk_postprocessing_tasks_document_operation_id",
        )
        if "ix_postprocessing_tasks_document_operation_id" not in _index_names(
            POSTPROCESSING_TASKS,
            column_name=NEW_ID,
        ):
            op.create_index("ix_postprocessing_tasks_document_operation_id", POSTPROCESSING_TASKS, [NEW_ID])
        if "uq_postprocessing_tasks_document_operation_task_kind" not in _unique_names(
            POSTPROCESSING_TASKS,
            constrained_column=NEW_ID,
        ):
            op.create_unique_constraint(
                "uq_postprocessing_tasks_document_operation_task_kind",
                POSTPROCESSING_TASKS,
                [NEW_ID, "task_kind"],
            )


def downgrade() -> None:
    if not _table_exists(SIMULATION_STEPS):
        return

    if OLD_ID not in _column_names(SIMULATION_STEPS):
        op.add_column(SIMULATION_STEPS, sa.Column(OLD_ID, sa.BigInteger(), nullable=True))
        op.execute(sa.text("UPDATE simulation_steps SET simulation_step_id = document_operation_id"))
        _ensure_column_not_null(SIMULATION_STEPS, OLD_ID)

    if _table_exists(SIMULATION_STEP_STATUS):
        if OLD_ID not in _column_names(SIMULATION_STEP_STATUS):
            op.add_column(SIMULATION_STEP_STATUS, sa.Column(OLD_ID, sa.BigInteger(), nullable=True))
            op.execute(
                sa.text(
                    """
                    UPDATE simulation_step_status AS status
                    SET simulation_step_id = step.simulation_step_id
                    FROM simulation_steps AS step
                    WHERE status.document_operation_id = step.document_operation_id
                    """
                )
            )
            _ensure_column_not_null(SIMULATION_STEP_STATUS, OLD_ID)
        _drop_foreign_keys(SIMULATION_STEP_STATUS, NEW_ID)
        if NEW_ID in _pk_columns(SIMULATION_STEP_STATUS):
            pk_name = _pk_name(SIMULATION_STEP_STATUS)
            if pk_name:
                op.drop_constraint(pk_name, SIMULATION_STEP_STATUS, type_="primary")
        if NEW_ID in _column_names(SIMULATION_STEP_STATUS):
            op.drop_column(SIMULATION_STEP_STATUS, NEW_ID)

    if _table_exists(POSTPROCESSING_TASKS):
        if OLD_ID not in _column_names(POSTPROCESSING_TASKS):
            op.add_column(POSTPROCESSING_TASKS, sa.Column(OLD_ID, sa.BigInteger(), nullable=True))
            op.execute(
                sa.text(
                    """
                    UPDATE postprocessing_tasks AS task
                    SET simulation_step_id = step.simulation_step_id
                    FROM simulation_steps AS step
                    WHERE task.document_operation_id = step.document_operation_id
                    """
                )
            )
            _ensure_column_not_null(POSTPROCESSING_TASKS, OLD_ID)
        _drop_foreign_keys(POSTPROCESSING_TASKS, NEW_ID)
        _drop_unique_constraints(POSTPROCESSING_TASKS, NEW_ID)
        _drop_indexes(POSTPROCESSING_TASKS, NEW_ID)
        if NEW_ID in _column_names(POSTPROCESSING_TASKS):
            op.drop_column(POSTPROCESSING_TASKS, NEW_ID)

    if NEW_ID in _pk_columns(SIMULATION_STEPS):
        pk_name = _pk_name(SIMULATION_STEPS)
        if pk_name:
            op.drop_constraint(pk_name, SIMULATION_STEPS, type_="primary")
    if _pk_columns(SIMULATION_STEPS) != [OLD_ID]:
        op.create_primary_key("simulation_steps_pkey", SIMULATION_STEPS, [OLD_ID])
    if not _unique_names(SIMULATION_STEPS, constrained_column=NEW_ID):
        op.create_unique_constraint("uq_simulation_steps_document_operation", SIMULATION_STEPS, [NEW_ID])

    if _table_exists(SIMULATION_STEP_STATUS):
        if _pk_columns(SIMULATION_STEP_STATUS) != [OLD_ID]:
            op.create_primary_key("simulation_step_status_pkey", SIMULATION_STEP_STATUS, [OLD_ID])
        if not _fk_names(SIMULATION_STEP_STATUS, constrained_column=OLD_ID):
            op.create_foreign_key(
                "simulation_step_status_simulation_step_id_fkey",
                SIMULATION_STEP_STATUS,
                SIMULATION_STEPS,
                [OLD_ID],
                [OLD_ID],
                ondelete="CASCADE",
            )

    if _table_exists(POSTPROCESSING_TASKS):
        if "ix_postprocessing_tasks_simulation_step_id" not in _index_names(
            POSTPROCESSING_TASKS,
            column_name=OLD_ID,
        ):
            op.create_index("ix_postprocessing_tasks_simulation_step_id", POSTPROCESSING_TASKS, [OLD_ID])
        if "uq_postprocessing_tasks_simulation_step_task_kind" not in _unique_names(
            POSTPROCESSING_TASKS,
            constrained_column=OLD_ID,
        ):
            op.create_unique_constraint(
                "uq_postprocessing_tasks_simulation_step_task_kind",
                POSTPROCESSING_TASKS,
                [OLD_ID, "task_kind"],
            )
        if not _fk_names(POSTPROCESSING_TASKS, constrained_column=OLD_ID):
            op.create_foreign_key(
                "postprocessing_tasks_simulation_step_id_fkey",
                POSTPROCESSING_TASKS,
                SIMULATION_STEPS,
                [OLD_ID],
                [OLD_ID],
                ondelete="CASCADE",
            )

"""add simulation runtime tables

Revision ID: 4f91c2a6b8d3
Revises: d2c6e8a4b9f1
Create Date: 2026-04-20 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4f91c2a6b8d3"
down_revision: Union[str, Sequence[str], None] = "d2c6e8a4b9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


simulation_step_status_enum = postgresql.ENUM(
    "blocked",
    "queued",
    "running",
    "finished",
    "failed",
    "cancelled",
    name="simulation_step_status_enum",
)

postprocessing_task_status_enum = postgresql.ENUM(
    "queued",
    "running",
    "finished",
    "failed",
    "cancelled",
    name="postprocessing_task_status_enum",
)

simulation_step_status_enum_no_create = postgresql.ENUM(
    "blocked",
    "queued",
    "running",
    "finished",
    "failed",
    "cancelled",
    name="simulation_step_status_enum",
    create_type=False,
)

postprocessing_task_status_enum_no_create = postgresql.ENUM(
    "queued",
    "running",
    "finished",
    "failed",
    "cancelled",
    name="postprocessing_task_status_enum",
    create_type=False,
)


def upgrade() -> None:
    simulation_step_status_enum.create(op.get_bind(), checkfirst=True)
    postprocessing_task_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "simulation_steps",
        sa.Column("simulation_step_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_version_id",
            sa.BigInteger(),
            sa.ForeignKey("document_versions.document_version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("execution_order", sa.Integer(), nullable=False),
        sa.Column(
            "source_block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blocks.block_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "block_type_id",
            sa.SmallInteger(),
            sa.ForeignKey("operations_library.type_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("block_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("library_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("material_version_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "press_id",
            sa.Integer(),
            sa.ForeignKey("presses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "press_mode_id",
            sa.Integer(),
            sa.ForeignKey("press_modes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "die_assembly_id",
            sa.Integer(),
            sa.ForeignKey("die_assemblies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "top_die_id",
            sa.Integer(),
            sa.ForeignKey("dies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "bottom_die_id",
            sa.Integer(),
            sa.ForeignKey("dies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "left_die_id",
            sa.Integer(),
            sa.ForeignKey("dies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "right_die_id",
            sa.Integer(),
            sa.ForeignKey("dies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parameter_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "control_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "step_specific_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "initial_geometry",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "final_geometry",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("accumulated_time_start_seconds", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("accumulated_time_stop_seconds", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "document_version_id",
            "execution_order",
            name="uq_simulation_steps_document_version_execution_order",
        ),
    )
    op.create_index(
        "ix_simulation_steps_document_version_id",
        "simulation_steps",
        ["document_version_id"],
    )
    op.create_index(
        "ix_simulation_steps_block_type_id",
        "simulation_steps",
        ["block_type_id"],
    )

    op.create_table(
        "simulation_step_status",
        sa.Column(
            "simulation_step_id",
            sa.BigInteger(),
            sa.ForeignKey("simulation_steps.simulation_step_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "status",
            simulation_step_status_enum_no_create,
            nullable=False,
            server_default=sa.text("'blocked'"),
        ),
        sa.Column(
            "simulation_server_id",
            sa.Integer(),
            sa.ForeignKey("servers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("worker_name", sa.String(length=255), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("simulation_percent", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("simulation_expected_duration_seconds", sa.Float(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "runtime_artifacts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "error_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_simulation_step_status_status",
        "simulation_step_status",
        ["status"],
    )
    op.create_index(
        "ix_simulation_step_status_simulation_server_id",
        "simulation_step_status",
        ["simulation_server_id"],
    )

    op.create_table(
        "postprocessing_tasks",
        sa.Column("postprocessing_task_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "simulation_step_id",
            sa.BigInteger(),
            sa.ForeignKey("simulation_steps.simulation_step_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_kind",
            sa.String(length=63),
            nullable=False,
            server_default=sa.text("'full'"),
        ),
        sa.Column(
            "status",
            postprocessing_task_status_enum_no_create,
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "postprocessing_server_id",
            sa.Integer(),
            sa.ForeignKey("servers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("worker_name", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "input_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("images_dir_path", sa.String(length=2047), nullable=True),
        sa.Column("pptx_file_name", sa.String(length=255), nullable=True),
        sa.Column("pdf_file_name", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "error_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "simulation_step_id",
            "task_kind",
            name="uq_postprocessing_tasks_simulation_step_task_kind",
        ),
    )
    op.create_index(
        "ix_postprocessing_tasks_simulation_step_id",
        "postprocessing_tasks",
        ["simulation_step_id"],
    )
    op.create_index(
        "ix_postprocessing_tasks_status",
        "postprocessing_tasks",
        ["status"],
    )
    op.create_index(
        "ix_postprocessing_tasks_postprocessing_server_id",
        "postprocessing_tasks",
        ["postprocessing_server_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_postprocessing_tasks_postprocessing_server_id", table_name="postprocessing_tasks")
    op.drop_index("ix_postprocessing_tasks_status", table_name="postprocessing_tasks")
    op.drop_index("ix_postprocessing_tasks_simulation_step_id", table_name="postprocessing_tasks")
    op.drop_table("postprocessing_tasks")

    op.drop_index("ix_simulation_step_status_simulation_server_id", table_name="simulation_step_status")
    op.drop_index("ix_simulation_step_status_status", table_name="simulation_step_status")
    op.drop_table("simulation_step_status")

    op.drop_index("ix_simulation_steps_block_type_id", table_name="simulation_steps")
    op.drop_index("ix_simulation_steps_document_version_id", table_name="simulation_steps")
    op.drop_table("simulation_steps")

    postprocessing_task_status_enum.drop(op.get_bind(), checkfirst=True)
    simulation_step_status_enum.drop(op.get_bind(), checkfirst=True)

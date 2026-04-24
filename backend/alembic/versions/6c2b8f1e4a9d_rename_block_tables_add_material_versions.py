"""rename block tables and add material versions

Revision ID: 6c2b8f1e4a9d
Revises: 4f91c2a6b8d3
Create Date: 2026-04-20 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c2b8f1e4a9d"
down_revision: Union[str, Sequence[str], None] = "4f91c2a6b8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("blocks", "document_blocks")
    op.rename_table("operations_library", "document_blocks_library")

    op.execute(
        """
        ALTER INDEX IF EXISTS ix_blocks_block_type_id
        RENAME TO ix_document_blocks_block_type_id
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS document_blocks
        RENAME CONSTRAINT blocks_pkey TO document_blocks_pkey
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS document_blocks_library
        RENAME CONSTRAINT operations_library_pkey TO document_blocks_library_pkey
        """
    )

    op.create_table(
        "material_versions",
        sa.Column("material_version_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("materials.material_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("name_snapshot", sa.String(length=1023), nullable=False),
        sa.Column("deform_file_name", sa.String(length=1023), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("material_id", "version_no", name="uq_material_versions_material_version_no"),
    )
    op.create_index("ix_material_versions_material_id", "material_versions", ["material_id"])

    op.execute(
        """
        INSERT INTO material_versions (
            material_id,
            version_no,
            name_snapshot,
            deform_file_name,
            note,
            created_at,
            updated_at
        )
        SELECT
            m.material_id,
            1,
            m.name,
            m.deform_file_name,
            m.note,
            now(),
            now()
        FROM materials AS m
        """
    )

    op.add_column("documents", sa.Column("material_version_id", sa.Integer(), nullable=True))
    op.create_index("ix_documents_material_version_id", "documents", ["material_version_id"])
    op.create_foreign_key(
        "fk_documents_material_version_id_material_versions",
        "documents",
        "material_versions",
        ["material_version_id"],
        ["material_version_id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE documents AS d
        SET material_version_id = mv.material_version_id
        FROM projects AS p
        JOIN material_versions AS mv
          ON mv.material_id = p.material_id
         AND mv.version_no = 1
        WHERE d.project_id = p.project_id
          AND d.material_version_id IS NULL
        """
    )

    op.alter_column(
        "simulation_steps",
        "material_version_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.create_index("ix_simulation_steps_material_version_id", "simulation_steps", ["material_version_id"])
    op.create_foreign_key(
        "fk_simulation_steps_material_version_id_material_versions",
        "simulation_steps",
        "material_versions",
        ["material_version_id"],
        ["material_version_id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE simulation_steps AS ss
        SET material_version_id = d.material_version_id
        FROM document_versions AS dv
        JOIN documents AS d
          ON d.document_id = dv.document_id
        WHERE ss.document_version_id = dv.document_version_id
          AND ss.material_version_id IS NULL
          AND d.material_version_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_simulation_steps_material_version_id_material_versions",
        "simulation_steps",
        type_="foreignkey",
    )
    op.drop_index("ix_simulation_steps_material_version_id", table_name="simulation_steps")
    op.alter_column(
        "simulation_steps",
        "material_version_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )

    op.drop_constraint(
        "fk_documents_material_version_id_material_versions",
        "documents",
        type_="foreignkey",
    )
    op.drop_index("ix_documents_material_version_id", table_name="documents")
    op.drop_column("documents", "material_version_id")

    op.drop_index("ix_material_versions_material_id", table_name="material_versions")
    op.drop_table("material_versions")

    op.execute(
        """
        ALTER TABLE IF EXISTS document_blocks_library
        RENAME CONSTRAINT document_blocks_library_pkey TO operations_library_pkey
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS document_blocks
        RENAME CONSTRAINT document_blocks_pkey TO blocks_pkey
        """
    )
    op.execute(
        """
        ALTER INDEX IF EXISTS ix_document_blocks_block_type_id
        RENAME TO ix_blocks_block_type_id
        """
    )

    op.rename_table("document_blocks_library", "operations_library")
    op.rename_table("document_blocks", "blocks")

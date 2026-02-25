"""Add library table and repoint projects.material_id FK

Revision ID: 9b9c2f4e7c31
Revises: dd3aff7dab58
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b9c2f4e7c31"
down_revision = "dd3aff7dab58"
branch_labels = None
depends_on = None


library_type_enum = sa.Enum(
    "die",
    "die_assembly",
    "press",
    "press_mode",
    "time_between_operations",
    "material",
    "operation_type",
    name="library_type_enum",
    native_enum=False,
)


def _drop_projects_material_fk_if_exists() -> None:
    op.execute(
        """
        DO $$
        DECLARE fk_name text;
        BEGIN
          SELECT tc.constraint_name
            INTO fk_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
          WHERE tc.table_name = 'projects'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'material_id'
          LIMIT 1;

          IF fk_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE projects DROP CONSTRAINT %I', fk_name);
          END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "library",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("type", library_type_enum, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("props", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_obsolete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["parent_id"], ["library.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_library_parent_id", "library", ["parent_id"], unique=False)
    op.create_index("ix_library_type", "library", ["type"], unique=False)

    # Seed material rows into library to keep existing project.material_id values valid.
    op.execute(
        """
        INSERT INTO library (id, parent_id, type, name, props, created_at, updated_at, is_obsolete)
        SELECT
          m.material_id,
          NULL,
          'material',
          LEFT(m.material_name, 255),
          json_build_object(
            'material_path', m.material_path,
            'short_name', m.short_name,
            'density', m.density
          ),
          COALESCE(m.created_at, NOW()),
          COALESCE(m.created_at, NOW()),
          FALSE
        FROM material AS m
        ON CONFLICT (id) DO NOTHING;
        """
    )
    op.execute(
        """
        SELECT setval(
          pg_get_serial_sequence('library', 'id'),
          COALESCE((SELECT MAX(id) FROM library), 1),
          true
        );
        """
    )

    _drop_projects_material_fk_if_exists()

    op.alter_column(
        "projects",
        "material_id",
        existing_type=sa.SmallInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="material_id::integer",
    )
    op.execute(
        """
        UPDATE projects
        SET material_id = NULL
        WHERE material_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM library WHERE library.id = projects.material_id
          );
        """
    )
    op.create_foreign_key(
        "fk_projects_material_id_library_id",
        "projects",
        "library",
        ["material_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_material_id_library_id", "projects", type_="foreignkey")

    op.alter_column(
        "projects",
        "material_id",
        existing_type=sa.Integer(),
        type_=sa.SmallInteger(),
        existing_nullable=True,
        postgresql_using="material_id::smallint",
    )
    op.execute(
        """
        UPDATE projects
        SET material_id = NULL
        WHERE material_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM material WHERE material.material_id = projects.material_id
          );
        """
    )
    op.create_foreign_key(
        "fk_projects_material_id_material_material_id",
        "projects",
        "material",
        ["material_id"],
        ["material_id"],
        ondelete="SET DEFAULT",
    )

    op.drop_index("ix_library_type", table_name="library")
    op.drop_index("ix_library_parent_id", table_name="library")
    op.drop_table("library")

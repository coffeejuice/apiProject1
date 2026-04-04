"""reshape materials table

Revision ID: 3a4d8f2c1b90
Revises: 9ac4e7b1d2f3
Create Date: 2026-03-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "3a4d8f2c1b90"
down_revision = "9ac4e7b1d2f3"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


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


def _drop_fk_constraints_for_column(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (fk.get("constrained_columns") or []) == [column_name] and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def _ensure_column(table_name: str, column_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    materials_table = "materials"
    if not _table_exists(materials_table):
        return

    _ensure_column(
        materials_table,
        "name",
        sa.Column("name", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    _ensure_column(
        materials_table,
        "source",
        sa.Column(
            "source",
            sa.String(length=63),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    _ensure_column(
        materials_table,
        "source_version",
        sa.Column(
            "source_version",
            sa.String(length=63),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    _ensure_column(
        materials_table,
        "file_name",
        sa.Column(
            "file_name",
            sa.String(length=1023),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    _ensure_column(
        materials_table,
        "properties",
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    _ensure_column(
        materials_table,
        "is_obsolete",
        sa.Column(
            "is_obsolete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    _ensure_column(
        materials_table,
        "obsolete_at",
        sa.Column("obsolete_at", sa.DateTime(), nullable=True),
    )
    _ensure_column(
        materials_table,
        "owner_id",
        sa.Column("owner_id", sa.Integer(), nullable=True),
    )

    if _table_exists("users") and not _fk_exists(materials_table, "owner_id", "users", "user_id"):
        op.create_foreign_key(
            "fk_materials_owner_id",
            materials_table,
            "users",
            ["owner_id"],
            ["user_id"],
            ondelete="SET NULL",
        )

    if _table_exists("library"):
        op.execute(
            """
            INSERT INTO materials (
              material_id,
              name,
              source,
              source_version,
              file_name,
              properties,
              is_obsolete,
              created_at,
              obsolete_at,
              owner_id
            )
            SELECT
              l.id,
              COALESCE(
                CASE
                  WHEN jsonb_typeof(l.props -> 'name') = 'object' THEN l.props -> 'name'
                  ELSE NULL
                END,
                jsonb_build_object('EN', l.name)
              ),
              COALESCE(NULLIF(l.props ->> 'source', ''), 'library'),
              COALESCE(l.props ->> 'source_version', ''),
              COALESCE(l.props ->> 'file_name', l.props ->> 'material_path', ''),
              CASE
                WHEN jsonb_typeof(l.props) = 'object' THEN
                  l.props - 'name' - 'source' - 'source_version' - 'file_name'
                ELSE '{}'::jsonb
              END,
              COALESCE(l.is_obsolete, false),
              COALESCE(l.created_at, now()),
              NULL,
              NULL
            FROM library AS l
            WHERE l.type = 'material'
              AND NOT EXISTS (
                SELECT 1
                FROM materials AS m
                WHERE m.material_id = l.id
              );
            """
        )

    if _column_exists(materials_table, "material_name"):
        op.execute(
            """
            UPDATE materials
            SET name = COALESCE(
              name,
              CASE
                WHEN material_name IS NOT NULL AND btrim(material_name) <> '' THEN jsonb_build_object('EN', material_name)
                ELSE jsonb_build_object('EN', concat('Material ', material_id))
              END
            );
            """
        )

    if _column_exists(materials_table, "material_path"):
        op.execute(
            r"""
            UPDATE materials
            SET file_name = COALESCE(
              NULLIF(file_name, ''),
              regexp_replace(COALESCE(material_path, ''), '^.*[\\/]', '')
            );
            """
        )
        op.execute(
            """
            UPDATE materials
            SET properties = COALESCE(properties, '{}'::jsonb) ||
              jsonb_strip_nulls(
                jsonb_build_object(
                  'legacy_material_path',
                  NULLIF(material_path, '')
                )
              );
            """
        )

    if _column_exists(materials_table, "short_name"):
        op.execute(
            """
            UPDATE materials
            SET properties = COALESCE(properties, '{}'::jsonb) ||
              jsonb_strip_nulls(
                jsonb_build_object(
                  'short_name',
                  NULLIF(short_name, '')
                )
              );
            """
        )

    if _column_exists(materials_table, "density"):
        op.execute(
            """
            UPDATE materials
            SET properties = COALESCE(properties, '{}'::jsonb) ||
              jsonb_strip_nulls(
                jsonb_build_object(
                  'density',
                  density
                )
              );
            """
        )

    op.execute(
        """
        UPDATE materials
        SET source = COALESCE(NULLIF(source, ''), 'legacy'),
            source_version = COALESCE(source_version, ''),
            file_name = COALESCE(file_name, ''),
            properties = COALESCE(properties, '{}'::jsonb),
            is_obsolete = COALESCE(is_obsolete, false),
            created_at = COALESCE(created_at, now())
        WHERE name IS NULL
           OR source IS NULL
           OR source_version IS NULL
           OR file_name IS NULL
           OR properties IS NULL
           OR is_obsolete IS NULL
           OR created_at IS NULL;
        """
    )
    op.execute(
        """
        UPDATE materials
        SET name = jsonb_build_object('EN', concat('Material ', material_id))
        WHERE name IS NULL;
        """
    )

    op.alter_column(materials_table, "name", existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=False)
    op.alter_column(materials_table, "source", existing_type=sa.String(length=63), nullable=False)
    op.alter_column(materials_table, "source_version", existing_type=sa.String(length=63), nullable=False)
    op.alter_column(materials_table, "file_name", existing_type=sa.String(length=1023), nullable=False)
    op.alter_column(
        materials_table,
        "properties",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
    )
    op.alter_column(materials_table, "is_obsolete", existing_type=sa.Boolean(), nullable=False)
    op.alter_column(materials_table, "created_at", existing_type=sa.DateTime(), nullable=False)

    if _table_exists("projects") and _column_exists("projects", "material_id"):
        if not _fk_exists("projects", "material_id", "materials", "material_id"):
            _drop_fk_constraints_for_column("projects", "material_id")
            op.execute(
                """
                UPDATE projects
                SET material_id = NULL
                WHERE material_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM materials
                    WHERE materials.material_id = projects.material_id
                  );
                """
            )
            op.create_foreign_key(
                "fk_projects_material_id_materials_material_id",
                "projects",
                "materials",
                ["material_id"],
                ["material_id"],
                ondelete="SET NULL",
            )

    for old_column in ("density", "short_name", "material_path", "material_name"):
        if _column_exists(materials_table, old_column):
            op.drop_column(materials_table, old_column)


def downgrade() -> None:
    materials_table = "materials"
    if not _table_exists(materials_table):
        return

    _ensure_column(
        materials_table,
        "material_name",
        sa.Column(
            "material_name",
            sa.String(length=2047),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    _ensure_column(
        materials_table,
        "material_path",
        sa.Column(
            "material_path",
            sa.String(length=2047),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    _ensure_column(
        materials_table,
        "short_name",
        sa.Column(
            "short_name",
            sa.String(length=63),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    _ensure_column(
        materials_table,
        "density",
        sa.Column("density", sa.Float(), nullable=True),
    )

    op.execute(
        """
        UPDATE materials
        SET material_name = COALESCE(
              NULLIF(material_name, ''),
              NULLIF(name ->> 'EN', ''),
              NULLIF(name ->> 'RU', ''),
              NULLIF(name ->> 'ZH_HANS', ''),
              concat('Material ', material_id)
            ),
            material_path = COALESCE(
              NULLIF(material_path, ''),
              NULLIF(properties ->> 'legacy_material_path', ''),
              file_name,
              ''
            ),
            short_name = COALESCE(
              NULLIF(short_name, ''),
              NULLIF(properties ->> 'short_name', ''),
              source,
              ''
            ),
            density = COALESCE(
              density,
              NULLIF(properties ->> 'density', '')::double precision
            );
        """
    )

    if _table_exists("projects") and _column_exists("projects", "material_id"):
        _drop_fk_constraints_for_column("projects", "material_id")
        if _table_exists("library"):
            op.execute(
                """
                UPDATE projects
                SET material_id = NULL
                WHERE material_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM library
                    WHERE library.id = projects.material_id
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

    if _column_exists(materials_table, "owner_id"):
        _drop_fk_constraints_for_column(materials_table, "owner_id")
        op.drop_column(materials_table, "owner_id")

    for new_column in ("obsolete_at", "is_obsolete", "properties", "file_name", "source_version", "source", "name"):
        if _column_exists(materials_table, new_column):
            op.drop_column(materials_table, new_column)

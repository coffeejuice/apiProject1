"""add material property tables

Revision ID: f7a2d4c8e1b3
Revises: e5d9c3a1b4f7
Create Date: 2026-04-07 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f7a2d4c8e1b3"
down_revision = "e5d9c3a1b4f7"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("materials_property_tables"):
        op.create_table(
            "materials_property_tables",
            sa.Column("table_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("test_record_id", sa.Integer(), nullable=False),
            sa.Column("property_type", sa.String(length=63), nullable=False),
            sa.Column(
                "representation_kind",
                sa.String(length=63),
                nullable=False,
                server_default=sa.text("'curve_2d'"),
            ),
            sa.Column("replicate_no", sa.Integer(), nullable=True),
            sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column(
                "is_obsolete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["test_record_id"],
                ["materials_test_records.test_record_id"],
                ondelete="CASCADE",
            ),
        )

    if not _table_exists("materials_property_table_to_columns_connectivity"):
        op.create_table(
            "materials_property_table_to_columns_connectivity",
            sa.Column("column_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("table_id", sa.Integer(), nullable=False),
            sa.Column("column_property_type", sa.String(length=63), nullable=False),
            sa.Column("column_units", sa.String(length=63), nullable=True),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.ForeignKeyConstraint(
                ["table_id"],
                ["materials_property_tables.table_id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "table_id",
                "sort_order",
                name="uq_mat_prop_tbl_cols_table_sort",
            ),
        )

    if not _table_exists("materials_property_column_values"):
        op.create_table(
            "materials_property_column_values",
            sa.Column("column_id", sa.Integer(), nullable=False),
            sa.Column("point_index", sa.Integer(), nullable=False),
            sa.Column("value", sa.Numeric(), nullable=True),
            sa.ForeignKeyConstraint(
                ["column_id"],
                ["materials_property_table_to_columns_connectivity.column_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("column_id", "point_index"),
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_materials_property_tables_updated_at()
        RETURNS TRIGGER
        AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_materials_test_records_from_property_tables()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                UPDATE materials_test_records
                SET updated_at = now()
                WHERE test_record_id = OLD.test_record_id;
                RETURN OLD;
            END IF;

            UPDATE materials_test_records
            SET updated_at = now()
            WHERE test_record_id = NEW.test_record_id;

            IF TG_OP = 'UPDATE' AND OLD.test_record_id IS DISTINCT FROM NEW.test_record_id THEN
                UPDATE materials_test_records
                SET updated_at = now()
                WHERE test_record_id = OLD.test_record_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_materials_property_tables_from_columns()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                UPDATE materials_property_tables
                SET updated_at = now()
                WHERE table_id = OLD.table_id;
                RETURN OLD;
            END IF;

            UPDATE materials_property_tables
            SET updated_at = now()
            WHERE table_id = NEW.table_id;

            IF TG_OP = 'UPDATE' AND OLD.table_id IS DISTINCT FROM NEW.table_id THEN
                UPDATE materials_property_tables
                SET updated_at = now()
                WHERE table_id = OLD.table_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_materials_property_tables_from_values()
        RETURNS TRIGGER
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                UPDATE materials_property_tables
                SET updated_at = now()
                FROM materials_property_table_to_columns_connectivity cols
                WHERE cols.column_id = OLD.column_id
                  AND materials_property_tables.table_id = cols.table_id;
                RETURN OLD;
            END IF;

            UPDATE materials_property_tables
            SET updated_at = now()
            FROM materials_property_table_to_columns_connectivity cols
            WHERE cols.column_id = NEW.column_id
              AND materials_property_tables.table_id = cols.table_id;

            IF TG_OP = 'UPDATE' AND OLD.column_id IS DISTINCT FROM NEW.column_id THEN
                UPDATE materials_property_tables
                SET updated_at = now()
                FROM materials_property_table_to_columns_connectivity cols
                WHERE cols.column_id = OLD.column_id
                  AND materials_property_tables.table_id = cols.table_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    if _table_exists("materials_property_tables"):
        op.execute("DROP TRIGGER IF EXISTS trg_set_materials_property_tables_updated_at ON materials_property_tables")
        op.execute(
            """
            CREATE TRIGGER trg_set_materials_property_tables_updated_at
            BEFORE UPDATE ON materials_property_tables
            FOR EACH ROW
            EXECUTE FUNCTION set_materials_property_tables_updated_at()
            """
        )
        op.execute("DROP TRIGGER IF EXISTS trg_touch_materials_test_records_from_property_tables ON materials_property_tables")
        op.execute(
            """
            CREATE TRIGGER trg_touch_materials_test_records_from_property_tables
            AFTER INSERT OR UPDATE OR DELETE ON materials_property_tables
            FOR EACH ROW
            EXECUTE FUNCTION touch_materials_test_records_from_property_tables()
            """
        )

    if _table_exists("materials_property_table_to_columns_connectivity"):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_touch_materials_property_tables_from_columns ON materials_property_table_to_columns_connectivity"
        )
        op.execute(
            """
            CREATE TRIGGER trg_touch_materials_property_tables_from_columns
            AFTER INSERT OR UPDATE OR DELETE ON materials_property_table_to_columns_connectivity
            FOR EACH ROW
            EXECUTE FUNCTION touch_materials_property_tables_from_columns()
            """
        )

    if _table_exists("materials_property_column_values"):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_touch_materials_property_tables_from_values ON materials_property_column_values"
        )
        op.execute(
            """
            CREATE TRIGGER trg_touch_materials_property_tables_from_values
            AFTER INSERT OR UPDATE OR DELETE ON materials_property_column_values
            FOR EACH ROW
            EXECUTE FUNCTION touch_materials_property_tables_from_values()
            """
        )


def downgrade() -> None:
    if _table_exists("materials_property_column_values"):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_touch_materials_property_tables_from_values ON materials_property_column_values"
        )
    if _table_exists("materials_property_table_to_columns_connectivity"):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_touch_materials_property_tables_from_columns ON materials_property_table_to_columns_connectivity"
        )
    if _table_exists("materials_property_tables"):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_touch_materials_test_records_from_property_tables ON materials_property_tables"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_set_materials_property_tables_updated_at ON materials_property_tables"
        )

    op.execute("DROP FUNCTION IF EXISTS touch_materials_property_tables_from_values()")
    op.execute("DROP FUNCTION IF EXISTS touch_materials_property_tables_from_columns()")
    op.execute("DROP FUNCTION IF EXISTS touch_materials_test_records_from_property_tables()")
    op.execute("DROP FUNCTION IF EXISTS set_materials_property_tables_updated_at()")

    if _table_exists("materials_property_column_values"):
        op.drop_table("materials_property_column_values")
    if _table_exists("materials_property_table_to_columns_connectivity"):
        op.drop_table("materials_property_table_to_columns_connectivity")
    if _table_exists("materials_property_tables"):
        op.drop_table("materials_property_tables")

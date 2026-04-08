"""add material chemistry tables

Revision ID: e5d9c3a1b4f7
Revises: c1f4e28b9a7d
Create Date: 2026-04-07 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5d9c3a1b4f7"
down_revision = "c1f4e28b9a7d"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("publications_catalog"):
        op.create_table(
            "publications_catalog",
            sa.Column("publication_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source_type", sa.String(length=63), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("authors_text", sa.Text(), nullable=True),
            sa.Column("publisher_or_journal", sa.String(length=255), nullable=True),
            sa.Column("issue_year", sa.Integer(), nullable=True),
            sa.Column("doi", sa.String(length=255), nullable=True),
            sa.Column("url", sa.String(length=2047), nullable=True),
            sa.Column("file_name", sa.String(length=1023), nullable=True),
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
        )

    if not _table_exists("materials_designations_standard_chemistry"):
        op.create_table(
            "materials_designations_standard_chemistry",
            sa.Column("standard_chemistry_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("designation_id", sa.Integer(), nullable=False),
            sa.Column("element_symbol", sa.String(length=16), nullable=False),
            sa.Column("min_wt_pct", sa.Float(), nullable=True),
            sa.Column("max_wt_pct", sa.Float(), nullable=True),
            sa.Column(
                "is_balance",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
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
                ["designation_id"],
                ["materials_designations.designation_id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "designation_id",
                "element_symbol",
                name="uq_mat_des_std_chem_desig_elem",
            ),
        )

    if not _table_exists("materials_test_records"):
        op.create_table(
            "materials_test_records",
            sa.Column("test_record_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("designation_id", sa.Integer(), nullable=True),
            sa.Column("publication_id", sa.Integer(), nullable=True),
            sa.Column("heat_number", sa.String(length=127), nullable=True),
            sa.Column("batch_number", sa.String(length=127), nullable=True),
            sa.Column("sample_label", sa.String(length=255), nullable=True),
            sa.Column("test_date", sa.Date(), nullable=True),
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
                ["material_id"],
                ["materials.material_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["designation_id"],
                ["materials_designations.designation_id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["publication_id"],
                ["publications_catalog.publication_id"],
                ondelete="SET NULL",
            ),
        )

    if not _table_exists("materials_chemistry_tests_results"):
        op.create_table(
            "materials_chemistry_tests_results",
            sa.Column("test_record_id", sa.Integer(), nullable=False),
            sa.Column("element_symbol", sa.String(length=16), nullable=False),
            sa.Column("actual_wt_pct", sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(
                ["test_record_id"],
                ["materials_test_records.test_record_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("test_record_id", "element_symbol"),
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_materials_test_records_updated_at()
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

    if _table_exists("materials_chemistry_tests_results"):
        op.execute("DROP TRIGGER IF EXISTS trg_touch_materials_test_records_updated_at ON materials_chemistry_tests_results")
        op.execute(
            """
            CREATE TRIGGER trg_touch_materials_test_records_updated_at
            AFTER INSERT OR UPDATE OR DELETE ON materials_chemistry_tests_results
            FOR EACH ROW
            EXECUTE FUNCTION touch_materials_test_records_updated_at()
            """
        )


def downgrade() -> None:
    if _table_exists("materials_chemistry_tests_results"):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_touch_materials_test_records_updated_at ON materials_chemistry_tests_results"
        )

    op.execute("DROP FUNCTION IF EXISTS touch_materials_test_records_updated_at()")

    if _table_exists("materials_chemistry_tests_results"):
        op.drop_table("materials_chemistry_tests_results")
    if _table_exists("materials_test_records"):
        op.drop_table("materials_test_records")
    if _table_exists("materials_designations_standard_chemistry"):
        op.drop_table("materials_designations_standard_chemistry")
    if _table_exists("publications_catalog"):
        op.drop_table("publications_catalog")

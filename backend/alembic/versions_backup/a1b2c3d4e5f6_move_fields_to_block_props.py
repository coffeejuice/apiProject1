"""move_fields_to_block_props

Revision ID: a1b2c3d4e5f6
Revises: 23f1d034f8bb
Create Date: 2026-01-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '23f1d034f8bb'
branch_labels = None
depends_on = None


def upgrade():
    """
    Move process fields to block props.
    These fields are now stored in the ProcessHeading block's props instead of the processes table.

    Step 1: Migrate data from processes table to ProcessHeading block props
    Step 2: Drop columns from processes table
    """
    from sqlalchemy import text

    # Get database connection
    connection = op.get_bind()

    # Step 1: Copy data from processes table to ProcessHeading block props
    # Find all ProcessHeading blocks and update their props with process data
    migration_query = text("""
        UPDATE blocks
        SET props = jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    jsonb_set(
                                        jsonb_set(
                                            jsonb_set(
                                                jsonb_set(
                                                    jsonb_set(
                                                        jsonb_set(
                                                            jsonb_set(
                                                                jsonb_set(
                                                                    jsonb_set(
                                                                        jsonb_set(
                                                                            props,
                                                                            '{heat_no}',
                                                                            to_jsonb(COALESCE(p.heat_no, ''))
                                                                        ),
                                                                        '{lot_no}',
                                                                        to_jsonb(COALESCE(p.lot_no, ''))
                                                                    ),
                                                                    '{finished_size}',
                                                                    to_jsonb(COALESCE(p.finished_size, ''))
                                                                ),
                                                                '{standard_customer}',
                                                                to_jsonb(COALESCE(p.standard_customer, ''))
                                                            ),
                                                            '{standard_wst}',
                                                            to_jsonb(COALESCE(p.standard_wst, ''))
                                                        ),
                                                        '{product_condition}',
                                                        to_jsonb(COALESCE(p.product_condition, ''))
                                                    ),
                                                    '{product_surface}',
                                                    to_jsonb(COALESCE(p.product_surface, ''))
                                                ),
                                                '{product_diameter_tolerance}',
                                                to_jsonb(COALESCE(p.product_diameter_tolerance, ''))
                                            ),
                                            '{product_length_tolerance}',
                                            to_jsonb(COALESCE(p.product_length_tolerance, ''))
                                        ),
                                        '{product_curvature_tolerance}',
                                        to_jsonb(COALESCE(p.product_curvature_tolerance, ''))
                                    ),
                                    '{stock_size}',
                                    to_jsonb(COALESCE(p.stock_size, ''))
                                ),
                                '{stock_weight}',
                                to_jsonb(COALESCE(p.stock_weight, 0.0))
                            ),
                            '{stock_no}',
                            to_jsonb(COALESCE(p.stock_no, ''))
                        ),
                        '{material_btt}',
                        to_jsonb(COALESCE(p.material_btt, 0.0))
                    ),
                    '{material_btt_sym_tolerance}',
                    to_jsonb(COALESCE(p.material_btt_sym_tolerance, 0.0))
                ),
                '{remarks}',
                to_jsonb(COALESCE(p.remarks, ''))
            ),
            '{preview_status}',
            to_jsonb(COALESCE(p.preview_status::text, 'empty'))
        )
        FROM processes p
        WHERE blocks.process_id = p.process_id
        AND blocks.block_type = 'process_heading'
        AND blocks.is_system = true
    """)

    connection.execute(migration_query)

    # Step 2: Drop columns from processes table
    op.drop_column('processes', 'heat_no')
    op.drop_column('processes', 'lot_no')
    op.drop_column('processes', 'finished_size')
    op.drop_column('processes', 'standard_customer')
    op.drop_column('processes', 'standard_wst')
    op.drop_column('processes', 'product_condition')
    op.drop_column('processes', 'product_surface')
    op.drop_column('processes', 'product_diameter_tolerance')
    op.drop_column('processes', 'product_length_tolerance')
    op.drop_column('processes', 'product_curvature_tolerance')
    op.drop_column('processes', 'stock_size')
    op.drop_column('processes', 'stock_weight')
    op.drop_column('processes', 'stock_no')
    op.drop_column('processes', 'material_btt')
    op.drop_column('processes', 'material_btt_sym_tolerance')
    op.drop_column('processes', 'remarks')
    op.drop_column('processes', 'preview_status')

    # Drop preview_status from process_versions as well
    op.drop_column('process_versions', 'preview_status')


def downgrade():
    """
    Restore columns to processes table (without data).
    This is for rollback only - data cannot be restored automatically.
    """
    # Add columns back to processes table
    op.add_column('processes', sa.Column('heat_no', sa.String(length=255), nullable=True))
    op.add_column('processes', sa.Column('lot_no', sa.String(length=255), nullable=True))
    op.add_column('processes', sa.Column('finished_size', sa.String(length=255), nullable=True))
    op.add_column('processes', sa.Column('standard_customer', sa.String(length=511), nullable=True))
    op.add_column('processes', sa.Column('standard_wst', sa.String(length=511), nullable=True))
    op.add_column('processes', sa.Column('product_condition', sa.String(length=7), nullable=True))
    op.add_column('processes', sa.Column('product_surface', sa.String(length=63), nullable=True))
    op.add_column('processes', sa.Column('product_diameter_tolerance', sa.String(length=63), nullable=True))
    op.add_column('processes', sa.Column('product_length_tolerance', sa.String(length=63), nullable=True))
    op.add_column('processes', sa.Column('product_curvature_tolerance', sa.String(length=63), nullable=True))
    op.add_column('processes', sa.Column('stock_size', sa.String(length=63), nullable=True))
    op.add_column('processes', sa.Column('stock_weight', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('processes', sa.Column('stock_no', sa.String(length=63), nullable=True))
    op.add_column('processes', sa.Column('material_btt', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('processes', sa.Column('material_btt_sym_tolerance', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('processes', sa.Column('remarks', sa.String(length=4095), nullable=True))
    op.add_column('processes', sa.Column('preview_status',
        postgresql.ENUM('empty', 'error', 'ok', 'ok_not_editable', name='preview_status_enum'),
        nullable=True))

    # Add preview_status back to process_versions
    op.add_column('process_versions', sa.Column('preview_status',
        postgresql.ENUM('empty', 'error', 'ok', 'ok_not_editable', name='preview_status_enum'),
        nullable=False,
        server_default='empty'))

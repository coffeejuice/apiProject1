"""rename_documents_table_to_processes

Revision ID: 08fa433142ab
Revises: 8d67e350b825
Create Date: 2026-01-19 18:05:47.164333

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08fa433142ab'
down_revision = '8d67e350b825'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename the table from 'documents' to 'processes'
    op.rename_table('documents', 'processes')


def downgrade() -> None:
    # Rename the table back from 'processes' to 'documents'
    op.rename_table('processes', 'documents')

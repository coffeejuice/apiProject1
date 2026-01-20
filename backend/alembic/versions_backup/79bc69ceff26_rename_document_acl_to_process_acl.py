"""rename_document_acl_to_process_acl

Revision ID: 79bc69ceff26
Revises: 08fa433142ab
Create Date: 2026-01-19 18:09:43.653240

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79bc69ceff26'
down_revision = '08fa433142ab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename the table from 'document_acl' to 'process_acl'
    op.rename_table('document_acl', 'process_acl')


def downgrade() -> None:
    # Rename the table back from 'process_acl' to 'document_acl'
    op.rename_table('process_acl', 'document_acl')

"""Initial complete schema

Revision ID: dd3aff7dab58
Revises: 
Create Date: 2026-01-21 00:17:33.580265

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd3aff7dab58'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Import all models to ensure they're registered with Base.metadata
    from app.database import Base
    import app.models

    # Get the bind (database connection)
    bind = op.get_bind()

    # Create all tables using SQLAlchemy's metadata
    # This will handle all dependencies and circular references correctly
    Base.metadata.create_all(bind)


def downgrade() -> None:
    # Import all models
    from app.database import Base
    import app.models

    # Get the bind (database connection)
    bind = op.get_bind()

    # Drop all tables
    Base.metadata.drop_all(bind)

"""Squashed current schema baseline

Revision ID: 9ac4e7b1d2f3
Revises:
Create Date: 2026-02-27 15:20:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "9ac4e7b1d2f3"
down_revision = None
branch_labels = None
depends_on = None


def _load_models() -> None:
    # Ensure all ORM tables are registered on Base.metadata.
    import app.models  # noqa: F401


def upgrade() -> None:
    from app.database import Base

    _load_models()
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    from app.database import Base

    _load_models()
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)

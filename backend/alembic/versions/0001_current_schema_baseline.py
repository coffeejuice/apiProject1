"""Current schema baseline.

Revision ID: 0001_current_schema
Revises:
Create Date: 2026-04-29 00:00:00.000000

This project is still pre-production, so the previous incremental migration
history was compacted into this single metadata-backed baseline. Existing
development databases that already match the current schema should be stamped
to this revision instead of replaying deleted historical migrations.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0001_current_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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

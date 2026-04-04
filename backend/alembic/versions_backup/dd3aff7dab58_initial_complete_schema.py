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


ACTIVE_SCHEMA_TABLES = (
    "users",
    "library",
    "material",
    "projects",
    "servers",
    "documents",
    "blocks",
    "document_edit_sessions",
    "document_versions",
    "settings",
)


def _load_active_models() -> None:
    """
    Import only models that back currently active backend/frontend flows.
    """
    from app.models.user import User  # noqa: F401
    from app.models.library.library_item import Library  # noqa: F401
    from app.models.library.material import Material  # noqa: F401
    from app.models.project import Project  # noqa: F401
    from app.models.server import Server  # noqa: F401
    from app.models.document.document import Document, DocumentEditSession, DocumentVersion  # noqa: F401
    from app.models.document.block import Block  # noqa: F401
    from app.models.settings import Setting  # noqa: F401


def _get_active_tables(metadata: sa.MetaData) -> list[sa.Table]:
    return [metadata.tables[name] for name in ACTIVE_SCHEMA_TABLES if name in metadata.tables]


def upgrade() -> None:
    from app.database import Base
    _load_active_models()

    bind = op.get_bind()
    tables = _get_active_tables(Base.metadata)

    # Create only active tables; legacy/obsolete tables are intentionally excluded.
    Base.metadata.create_all(bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    from app.database import Base
    _load_active_models()

    bind = op.get_bind()
    tables = _get_active_tables(Base.metadata)

    Base.metadata.drop_all(bind, tables=tables, checkfirst=True)

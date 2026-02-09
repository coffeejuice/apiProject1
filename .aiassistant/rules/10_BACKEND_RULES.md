---
apply: always
---

# Backend Rules

## Stack
- Python 3.11
- FastAPI (see backend/requirements.txt for exact versions)
- SQLAlchemy 2.x (sync ORM)
- Alembic migrations
- Pydantic v2 schemas
- JWT auth (OAuth2 password flow)

## Key directories
- backend/app/models/        ORM models (users, documents, blocks, revisions)
- backend/app/routers/       API endpoints
- backend/app/services/      Business logic (commit, search, import/export)
- backend/app/schemas.py     Pydantic schemas
- backend/run.py             Uvicorn entry point
- backend/scripts/           Maintenance and utility scripts
- backend/tests/             Backend test suite

## Environment
- Keep backend/.env out of version control; use backend/.env.example as a template.

## Domain rules
- Blocks are ordered by lexicographic `order_key` and store type-specific data in JSON `props`.
- Revisions are immutable history records.

## Guardrails
- Always filter soft-deleted rows unless explicitly including deleted (`deleted_at IS NULL`).
- Update `app/schemas.py` with any model changes.
- Enforce access control via `DocumentACL` or `ShareLink` on mutations.
- Follow `BlockType` enum definitions when adding or updating block types.

## Migration policy
- This repo favors a single consolidated migration file.
- When schema changes:
  - Back up existing migration files.
  - Delete `backend/alembic/versions/*.py`.
  - Create a new revision and use `Base.metadata.create_all()` in upgrade.

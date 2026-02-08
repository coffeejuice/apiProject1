# Backend Quickstart (Windows)

## Rules
- Backend runs on port 8001.
- Use DATABASE_URL with the postgresql+psycopg scheme.
- Keep .env out of version control.

## Start the server
1) cd backend
2) .venv\Scripts\activate
3) python run.py

API: http://localhost:8001
Docs: http://localhost:8001/docs

## First-time setup
See backend/SETUP.md for full setup steps.

## Common commands
- python -m alembic current
- python -m client.cli register <username> <email>
- python -m client.cli login <username>
- python -m client.cli create "My First Document"

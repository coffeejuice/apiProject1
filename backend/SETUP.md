# Backend Setup and Operations

## Rules
- Backend runs on port 8001.
- Use PostgreSQL with the postgresql+psycopg scheme.
- Keep .env files out of version control.

## Prerequisites
- Python 3.11
- PostgreSQL 13+ (local Windows install)
- Windows OS

## Installation
1) Create and activate a virtual environment:
   python -m venv .venv
   .venv\Scripts\activate
2) Install dependencies:
   pip install -r requirements.txt

## Configure environment
Create backend/.env:
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/notion_db
SECRET_KEY=<random string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

Generate a SECRET_KEY:
python -c "import secrets; print(secrets.token_urlsafe(32))"

## Create the database
python setup_database.py

## Run migrations
python -m alembic upgrade head

## Start the server
python run.py

API: http://localhost:8001
Docs: http://localhost:8001/docs

## Common operations
- Check migration status:
  python -m alembic current
- Migration history:
  python -m alembic history
- New migration (if needed):
  python -m alembic revision -m "Schema update"
- Reset database (destructive):
  python setup_database.py
  python -m alembic upgrade head

## Troubleshooting
PostgreSQL connection issues:
- Ensure the PostgreSQL service is running.
- Verify DATABASE_URL in backend/.env.
- Test with: psql -U <user> -h localhost

Import errors:
- Activate the virtual environment.
- Reinstall deps: pip install -r requirements.txt

Port in use:
- Free port 8001; avoid 8000 on Windows.

Migration errors:
- If a revision is missing, reset migrations per the migration policy.

## Production notes (short)
- Use system environment variables instead of .env files.
- Enable HTTPS and restrict DB access.
- Configure CORS in backend/app/main.py.
- Set up backups and log rotation.

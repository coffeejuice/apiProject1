# Backend Windows Quickstart

## Prerequisites
- Python 3.11+
- PostgreSQL 13+ (local install)
- Git (optional)

## Setup
1) python -m venv .venv
2) .venv\Scripts\activate
3) pip install -r requirements.txt
4) Create backend/.env:
   DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/notion_db
   SECRET_KEY=<random string>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
5) python setup_database.py
6) python -m alembic upgrade head

## Run the API
python run.py

API: http://localhost:8001
Docs: http://localhost:8001/docs

## Common commands
- python -m alembic current
- python -m alembic history
- python -m client.cli register <username> <email>
- python -m client.cli login <username>
- python -m client.cli list

## Troubleshooting
- PostgreSQL not running: start the Windows service (services.msc).
- Port conflict: free port 8001 and keep it for the API.
- Import errors: activate the virtual environment.

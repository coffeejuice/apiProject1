---
apply: always
---

# Backend Workflow

## Setup (Windows)
1) cd backend
2) python -m venv .venv
3) .venv\Scripts\activate
4) pip install -r requirements.txt
5) Create backend/.env:
   DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/notion_db
   SECRET_KEY=<random string>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
6) python ..\setup\setup_database.py
7) python -m alembic upgrade head
8) python run.py  # http://localhost:8001

Note: Run setup scripts from backend so backend/.env is loaded and app imports resolve.

## Common commands
- Check migrations: python -m alembic current
- Migration history: python -m alembic history
- New migration: python -m alembic revision -m "Schema update"
- Initialize database: python ..\setup\setup_database.py
- Reset database (destructive): python ..\setup\reinit_db.py
- Recreate settings table: python ..\setup\recreate_settings_table.py
- Run SQL migration file: python ..\setup\run_migration.py <migration_file>

## Troubleshooting
- Ensure PostgreSQL service is running.
- If port 8001 is in use, free it and keep 8001.
- Import errors usually mean the virtual environment is not activated.

## Production notes (short)
- Use env vars instead of .env files.
- Enable HTTPS and restrict database access.
- Configure CORS in backend/app/main.py.

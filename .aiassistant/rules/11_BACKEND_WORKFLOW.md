---
apply: always
---

# Backend Workflow

## Common commands
- Check migrations: python -m alembic current
- Migration history: python -m alembic history
- New migration: python -m alembic revision -m "Schema update"
- Initialize database: python setup_database.py
- Reset database (destructive): python db_setup/reinit_db.py
- Recreate settings table: python db_setup/recreate_settings_table.py
- Run SQL migration file: python db_setup/run_migration.py <migration_file>

## Troubleshooting
- Ensure PostgreSQL service is running.
- If port 8001 is in use, free it and keep 8001.
- Import errors usually mean the virtual environment is not activated.

## Production notes (short)
- Use env vars instead of .env files.
- Enable HTTPS and restrict database access.
- Configure CORS in backend/app/main.py.

---
apply: always
---

# Project Setup

## Local development (Linux)
Backend:
1) Use Python 3.12
2) sudo apt-get update && sudo apt-get install -y build-essential python3.12-dev
3) sudo apt install python3.12-venv
4) cd backend
5) python3 -m venv .venv
6) source .venv/bin/activate
7) Give passwordless sudo for the specific commands (most common):
   sudo visudo
   then add:
   alextub ALL=(root) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/dpkg
8) pip install 'vtk<9.5'
9) pip install setuptools
10) pip install --no-cache-dir --no-build-isolation -v mayavi
11) pip install -r requirements.txt
12) Generate a SECRET_KEY:
    python -c "import secrets; print(secrets.token_urlsafe(32))"
12) Create backend/.env:
   DATABASE_URL=postgresql+psycopg://notion_sys_user:pass@localhost:5432/notion_db
   SECRET_KEY=<random string>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
13) python setup_database.py
14) python -m alembic upgrade head
15) python run.py  # http://localhost:8001

Note: Run setup scripts from backend so backend/.env is loaded and app imports resolve.

Frontend:
1) Install Node.js 18+.
2) cd frontend
3) npm install
4) npm run dev  # http://localhost:5173

## Build and checks
- npm run build
- npm run preview
- npm run lint
- npm run typecheck

## Required environment variables (backend/.env)
DB_ADMIN_URL=postgresql+psycopg://postgres:password@127.0.0.1:5432/postgres
DATABASE_URL=postgresql+psycopg://notion_sys_user:password@localhost:5432/notion_db
SECRET_KEY=<random string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

## Common commands
Backend:
- python run.py
- python -m alembic current
- python -m alembic history

Frontend:
- npm run dev
- npm run build
- npm run preview
- npm run lint
- npm run typecheck

## Integration notes
- Frontend default API base URL: http://127.0.0.1:8001
- Auth uses JWT bearer tokens stored in localStorage.
- If a test user is created via backend/scripts/create_test_user.py:
  - username: demo_user
  - password: password123

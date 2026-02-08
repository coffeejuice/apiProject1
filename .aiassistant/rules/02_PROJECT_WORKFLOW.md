---
apply: always
---

# Project Workflow

## Local development (Windows)
Backend:
1) cd backend
2) python -m venv .venv
3) .venv\Scripts\activate
4) pip install -r requirements.txt
5) Create backend/.env with DATABASE_URL and SECRET_KEY
6) python setup_database.py
7) python -m alembic upgrade head
8) python run.py  # http://localhost:8001

Frontend:
1) cd frontend
2) npm install
3) npm run dev  # http://localhost:5173

## Required environment variables (backend/.env)
- DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/notion_db
- SECRET_KEY=<random string>
- ALGORITHM=HS256
- ACCESS_TOKEN_EXPIRE_MINUTES=30

Generate a SECRET_KEY:
python -c "import secrets; print(secrets.token_urlsafe(32))"

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
- If a test user is created via backend/create_test_user.py:
  - username: testuser
  - password: password123

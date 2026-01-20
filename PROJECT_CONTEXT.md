# 🤖 PROJECT_CONTEXT: Techno-Notion API (Monorepo)

## 🏗️ Monorepo Structure
```
apiProject1/
├── backend/           # FastAPI backend server (Python, port 8001)
├── frontend/          # React + TypeScript web frontend (Vite, port 5173)
├── frontend_obsolete/ # Archived Qt/QML and PySide6 clients (not maintained)
├── scripts/           # Shared build/deployment scripts
├── contracts/         # API contracts & TypeScript types (TBD)
├── .env.example       # Environment template
└── PROJECT_CONTEXT.md # This file
```

## 🏛 Systems Overview
Industrial-grade process management API. Notion-style block architecture focused on versioned simulation data.

## 🛠 Tech Stack
### Backend
- **Runtime**: Python 3.10+ | FastAPI 0.128+
- **Database**: PostgreSQL | SQLAlchemy 2.0 (Sync/Mapped) | Alembic Migrations
- **Auth**: JWT (OAuth2 Password flow) | Bcrypt
- **Modeling**: Pydantic v2 (Schemas in `backend/app/schemas.py`)
- **Transport**: Uvicorn | Port 8001 (Port 8000 is reserved on Windows systems)

### Frontend
- **Framework**: React 18.3 with TypeScript
- **Build Tool**: Vite (dev server on port 5173)
- **Styling**: Tailwind CSS 3.4 + @tailwindcss/typography
- **Editor**: TipTap 2.2 (ProseMirror-based rich text editor)
- **State**: Zustand 4.5 (lightweight state management)
- **Routing**: React Router 6.28
- **See**: `frontend/FRONTEND_CONTEXT.md` for detailed architecture

### Frontend (Archived)
- **Obsolete Clients**: PySide6 6.10+ | Qt Quick (QML) - See `frontend_obsolete/`

## 🏢 Core Mental Model
1. **Processes** (Table: `processes`): The root entity or "Page". Also called "documents" in API endpoints.
2. **Blocks** (Table: `blocks`): Polymorphic components (Text, Table, Image, etc.).
   - **Ordering**: Lexicographical `order_key` (allows O(1) inserts/moves).
   - **Props**: Type-specific data in JSON `props` field.
3. **Revisions** (Table: `revisions`): Immutable change history.
4. **Users** (Table: `users`): User accounts with authentication.
5. **Library**: Industrial assets like `material`, `die`, `press`.

## 📂 Backend Architecture Map
### `/backend/app` (Core logic)
- `models/user.py`: User accounts, devices, authentication.
- `models/document/`: `process.py` (Root), `block.py` (Atomic elements), `revision.py`.
- `models/library/`: `material.py`, `die.py`, `press.py` (Industrial entities).
- `services/`: `commit_service.py` (Revision management logic), `block_service.py`.
- `routers/`: Resource endpoints (auth, sharing, process, search).
- `schemas.py`: Pydantic models for API validation.

### `/backend` (Entry points & config)
- `run.py`: API server entry point (Uvicorn on :8001).
- `setup_database.py`: Database creation script (PostgreSQL).
- `reinit_db.py`: Database reset/initialization script.
- `requirements.txt`: Python dependencies.
- `alembic/`: Database migrations (single consolidated migration).
- `.env`: Environment configuration (DATABASE_URL, SECRET_KEY, etc.).
- `.venv/`: Python virtual environment (backend-specific).

## ⚙️ Networking & Environment
- **API_URL**: `http://localhost:8001`
- **Port Note**: CRITICAL - Always use 8001. Port 8000 often conflicts with Windows services.
- **Database**: PostgreSQL configured via `backend/.env`
  - Format: `postgresql+psycopg://user:password@localhost:5432/notion_db`
  - Driver: `psycopg` (v3, pure Python implementation)
- **Environment Variables**:
  - `DATABASE_URL`: PostgreSQL connection string
  - `SECRET_KEY`: JWT signing key (generate with `secrets.token_urlsafe(32)`)
  - `ALGORITHM`: JWT algorithm (default: HS256)
  - `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration (default: 30)

## ⚠️ Implementation Guardrails
1. **Soft Deletes**: Always filter for `deleted_at IS NULL` on read.
2. **Schema-First**: Update `app/schemas.py` synchronously with model changes.
3. **Migrate**: For DB schema changes, modify models then regenerate the single migration:
   - Delete `backend/alembic/versions/*.py` (backup first)
   - Create new: `alembic revision -m "Schema update"`
   - Use `Base.metadata.create_all()` in upgrade function
4. **Access Control**: Verify `ProcessACL` or `ShareLink` for mutations.
5. **JSON Props**: Follow `BlockType` enum definitions in `block.py` strictly.
6. **User Model**: Table is `users` (not `accounts`), removed `department_id`, `language_id` → `language_code`.

## 🚀 Common Commands
```powershell
# Backend: Initial Setup
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with DATABASE_URL and SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"  # Generate SECRET_KEY

# Setup database
python setup_database.py  # Creates empty database
alembic upgrade head       # Runs migrations

# Backend: Start API server
.venv\Scripts\python run.py

# Frontend: Start development server
cd frontend
npm install        # First time only
npm run dev        # Runs on http://localhost:5173

# Frontend: Build for production
cd frontend
npm run build
npm run preview
```

## 🔑 Development Notes

### Frontend-Backend Integration
- **API Base URL**: `http://127.0.0.1:8001` (configurable in frontend login page)
- **Authentication**: JWT tokens stored in localStorage
- **Data Persistence**:
  - Document titles → Backend database (via PATCH `/documents/{id}`)
  - Editor content → LocalStorage only (operational transform not implemented)
  - Search → Backend title search (via POST `/search`)

### Test Credentials
- **Username**: testuser
- **Password**: password123
- Created with `backend/create_test_user.py`

### Critical Implementation Details
1. **API Endpoints use `/documents`** - Database table is `processes`, but API routes remain `/documents/*`
2. **User Table is `users`** - Changed from `accounts` to `users` throughout the project
3. **Backend Commit System** - Frontend does NOT implement operational transform pattern (insert_block, update_text, etc.)
4. **Field Normalization** - Backend returns `process_id` (integer), frontend maps to `id` (string)
5. **Port 8001 is Critical** - Port 8000 often conflicts with Windows services
6. **Database Schema Changes**:
   - Table `accounts` → `users`
   - Removed `department_id` column and `departments` table
   - Changed `language_id` (SMALLINT) → `language_code` (VARCHAR(8))
   - Removed `editor_append_mode_id` and `process_version_id` from users table
   - Changed `user_settings` from VARCHAR(32767) → TEXT

### Documentation
- Backend: See individual files in `backend/` for API documentation
- Frontend: See `frontend/FRONTEND_CONTEXT.md` for detailed architecture
- Obsolete Clients: See `frontend_obsolete/` for archived Qt/QML implementations
```

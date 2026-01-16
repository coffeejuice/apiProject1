# 🤖 PROJECT_CONTEXT: Techno-Notion API

## 🏛 Systems Overview
Industrial-grade process management API. Notion-style block architecture focused on versioned simulation data.

## 🛠 Tech Stack
- **Runtime**: Python 3.10+ | FastAPI 0.128+
- **Database**: PostgreSQL | SQLAlchemy 2.0 (Sync/Mapped) | Alembic Migrations
- **Auth**: JWT (OAuth2 Password flow) | Bcrypt
- **Modeling**: Pydantic v2 (Schemas in `app/schemas.py`)
- **Transport**: Uvicorn | Port 8001 (Port 8000 is reserved on Windows systems)
- **GUI**: PySide6 6.10+ | Qt Quick (QML)

## 🏢 Core Mental Model
1. **Processes** (Table: `documents`): The root entity or "Page".
2. **Blocks** (Table: `blocks`): Polymorphic components (Text, Table, Image, etc.).
   - **Ordering**: Lexicographical `order_key` (allows O(1) inserts/moves).
   - **Props**: Type-specific data in JSON `props` field.
3. **Revisions** (Table: `revisions`): Immutable change history.
4. **Library**: Industrial assets like `material`, `die`, `press`.

## 📂 Architecture Map
### `/app` (Core logic)
- `models/document/`: `process.py` (Root), `block.py` (Atomic elements).
- `models/library/`: `material.py`, `die.py`, `press.py` (Industrial entities).
- `services/`: `commit_service.py` (Revision management logic), `block_service.py`.
- `routers/`: Resource endpoints (auth, sharing, process, search).

### `/gui_client_v2` (Modern Client)
- **Architecture**: MVVM+S (Model-View-ViewModel-Service).
- **Core Logic**: `app/viewmodels/` (Process, Block, List), `app/core/registry.py` (Dynamic block loading).
- **UI**: `resources/qml/` (Main, Sidebar, modular Blocks).

### `/client` & Root
- `gui_client.py`: Legacy PySide6/PyQt Desktop UI.
- `run.py`: Entry point (Uvicorn on :8001).
- `example.py`: Full lifecycle demonstration script.

## ⚙️ Networking & Environment
- **API_URL**: `http://localhost:8001`
- **Port Note**: CRITICAL - Always use 8001. Port 8000 often conflicts with Windows services.
- **Database**: Configured via `.env` (PostgreSQL).

## ⚠️ Implementation Guardrails
1. **Soft Deletes**: Always filter for `deleted_at IS NULL` on read.
2. **Schema-First**: Update `app/schemas.py` synchronously with model changes.
3. **Migrate**: Use `alembic revision --autogenerate` for any DB schema changes.
4. **Access Control**: Verify `ProcessACL` or `ShareLink` for mutations.
5. **JSON Props**: Follow `BlockType` enum definitions in `block.py` strictly.

## 🚀 Common Commands
```powershell
# Start API
python run.py

# Start GUI (v2)
cd gui_client_v2; python main.py

# Migration
alembic upgrade head
```

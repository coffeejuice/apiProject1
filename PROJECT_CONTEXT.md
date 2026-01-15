# 🤖 Project Context: Techno-Notion API

High-density technical blueprint for industrial process management and simulation.

## 🛠 Tech Stack & Constraints
- **Core**: Python 3.10+, FastAPI 0.128.0+, SQLAlchemy 2.0 (Sync/Mapped).
- **DB**: PostgreSQL (Alembic for migrations).
- **Auth**: JWT (OAuth2 Password flow), Bcrypt hashing.
- **Validation**: Pydantic v2 (Schemas in `app/schemas.py`).
- **Dev Tools**: Uvicorn (standard), Requests (for testing).

## 📐 Architecture & Logic
- **Pattern**: `Router` (entry) -> `Service` (logic) -> `Model/Schema` (data).
- **Document Model**: 
    - `Process` (table: `documents`): The root entity.
    - `Block` (table: `blocks`): Polymorphic-like records. Type-specific data stored in `props` JSON field.
    - `Revision`: Immutable change history for all block/document mutations.
    - `ProcessVersion`: Point-in-time snapshots for simulation and release management.
- **Order Mechanism**: Blocks use `order_key` for lexicographical sorting (allows O(1) inserts between blocks).

## 📂 Source Map
- `app/models/document/`: Core domain logic (`process.py`, `block.py`).
- `app/models/library/`: Industrial assets (`material.py`, `die.py`).
- `app/routers/`: Resource endpoints (auth, sharing, process, search).
- `app/services/`: Reusable business logic/orchestration.
- `gui_client.py`: Primary Desktop GUI application for end-users.
- `client/`: CLI implementation for automation and integration testing.

## 🕹 Standard Operating Procedures (SOPs)

### Server & UI Startup
```powershell
# 1. Start Backend API
python run.py

# 2. Start GUI Client (Primary User Interface)
python gui_client.py
```

### Scripting & CLI Testing
```powershell
# Run Demo Flow
python example.py

# CLI Testing (Secondary/Automation)
python -m client.cli login <username>
```

## 📝 Agent Guidelines
1. **Schema Consistency**: Always update `app/schemas.py` when modifying models.
2. **Migration Discipline**: Ensure every DB change has an accompanying Alembic file.
3. **Implicit Filtering**: Many queries should filter by `deleted_at IS NULL` (soft-delete support).
4. **Permissions**: Always check `ProcessACL` or `ShareLink` before modifying data.
5. **Block Typing**: Follow `BlockType` enum in `app/models/document/block.py` strictly.

# Techno-Notion API - Monorepo

> Industrial-grade process management system with Notion-style block architecture for versioned simulation data.

## 📁 Repository Structure

```
apiProject1/
├── backend/              # FastAPI REST API server
│   ├── app/             # Core application logic
│   ├── alembic/         # Database migrations
│   ├── run.py           # Server entry point
│   ├── requirements.txt # Python dependencies
│   └── .venv/           # Python virtual environment
├── frontend/             # Frontend application (TBD)
├── frontend_obsolete/    # Archived Qt/QML clients (not maintained)
├── scripts/              # Shared build/deployment scripts
├── contracts/            # API contracts & TypeScript types (TBD)
└── .env.example          # Environment configuration template
```

## 🚀 Quick Start

### Backend Setup

1. **Navigate to backend directory:**
   ```powershell
   cd backend
   ```

2. **Create virtual environment and install dependencies:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   Copy `.env.example` from root to `backend/.env` and update with your PostgreSQL credentials:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/notion_db
   SECRET_KEY=<generate-secure-key>
   ```

4. **Setup database:**
   ```powershell
   python setup_database.py
   alembic upgrade head
   ```

5. **Start the server:**
   ```powershell
   python run.py
   ```

   API available at: **http://localhost:8001**
   Interactive docs: **http://localhost:8001/docs**

### Frontend Setup

Frontend implementation is planned. Legacy clients are archived in `frontend_obsolete/`.

## 📚 Documentation

- **[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)** - System architecture and technical overview
- **[backend/QUICKSTART_WINDOWS.md](backend/QUICKSTART_WINDOWS.md)** - Windows-specific setup guide
- **[backend/SETUP.md](backend/SETUP.md)** - Detailed backend setup and configuration
- **[backend/START_HERE.md](backend/START_HERE.md)** - Quick reference guide

## 🛠 Technology Stack

### Backend
- **Runtime:** Python 3.10+
- **Framework:** FastAPI 0.128+
- **Database:** PostgreSQL with SQLAlchemy 2.0
- **Migrations:** Alembic
- **Authentication:** JWT (OAuth2) with Bcrypt
- **Validation:** Pydantic v2
- **Server:** Uvicorn (Port 8001)

### Frontend
- **Status:** TBD
- **Archived Clients:** PySide6/Qt Quick (QML) - see `frontend_obsolete/`

## 🏢 Core Concepts

- **Processes** - Root entities (documents/pages)
- **Blocks** - Polymorphic content components (text, tables, images)
- **Revisions** - Immutable change history with version control
- **Library** - Industrial assets (materials, dies, presses)

## ⚙️ Development

### Backend Commands

```powershell
# Start development server
cd backend
.venv\Scripts\python run.py

# Run example/demo script
cd backend
.venv\Scripts\python example.py

# Database migrations
cd backend
alembic upgrade head                           # Apply migrations
alembic revision --autogenerate -m "message"  # Create new migration
alembic current                                # Check current version

# Database management
python setup_database.py                       # Initialize database
python reinit_db.py                           # Reset database (WARNING: deletes data)
```

### Testing the API

**Option 1: Interactive Documentation**
- Visit http://localhost:8001/docs

**Option 2: Example Script**
```powershell
cd backend
python example.py
```

**Option 3: Direct API Calls**
```powershell
# Register user
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "password123"}'

# Login
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123"}'
```

## 📝 API Endpoints

Full API documentation available at http://localhost:8001/docs

**Key endpoints:**
- `POST /auth/register` - Register new user
- `POST /auth/login` - User authentication
- `POST /documents` - Create process/document
- `GET /documents` - List all documents
- `POST /documents/{id}/commit` - Commit block changes
- `GET /documents/{id}/blocks/root` - Get root blocks
- `GET /search` - Full-text search
- `GET /documents/{id}/export` - Export to Markdown

## 🔧 Configuration

### Environment Variables

Create `backend/.env` with the following:

```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/notion_db
SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_urlsafe(32))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Port Configuration

**Important:** The server uses **port 8001** (not 8000) as port 8000 is often reserved by Windows services.

## 🗂️ Monorepo Organization

### Backend (`/backend`)
Complete FastAPI application with database models, API routes, business logic, and migrations.

### Frontend (`/frontend`)
Reserved for future web/mobile frontend implementation.

### Frontend Obsolete (`/frontend_obsolete`)
Archived Qt/QML desktop clients:
- `gui_client.py` - Legacy PySide6 client
- `gui_client_v2/` - MVVM architecture client
- `gui_client_example_cpp/` - C++ Qt Quick client

These are preserved for reference but not actively maintained.

### Scripts (`/scripts`)
Shared automation scripts for building, testing, and deployment (TBD).

### Contracts (`/contracts`)
API type definitions and contracts for frontend-backend integration (TBD).

## 🚨 Troubleshooting

### PostgreSQL Connection Issues
1. Verify PostgreSQL service is running (Services → postgresql-x64-XX)
2. Check credentials in `backend/.env`
3. Test connection: `psql -U postgres -h localhost`

### Port Already in Use
If port 8001 is occupied, change in `backend/run.py`:
```python
uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
```

### Module Import Errors
Ensure virtual environment is activated:
```powershell
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
```

## 📦 Requirements

- **Python:** 3.10+
- **PostgreSQL:** 13+ (local installation)
- **OS:** Windows (development), Linux (production)
- **Disk Space:** 500MB+ (including dependencies and database)

## 🔒 Security Notes

⚠️ **For Production Deployment:**
- Generate strong `SECRET_KEY`
- Use HTTPS with reverse proxy (nginx/Apache)
- Implement rate limiting
- Configure CORS properly
- Use environment variables (not `.env` file)
- Enable database connection pooling
- Set up monitoring and logging
- Regular security updates

## 📖 Next Steps

1. **Backend:** See `backend/README.md` or `backend/START_HERE.md`
2. **API Exploration:** Visit http://localhost:8001/docs
3. **Frontend Development:** Plan your frontend stack in `/frontend`
4. **Contracts:** Define API types in `/contracts`

## 📄 License

MIT

## 🤝 Contributing

Contributions welcome! Please submit pull requests or open issues.

---

**Built with FastAPI, SQLAlchemy, and PostgreSQL**

For detailed backend documentation, see `backend/` directory.

# Quick Start Guide for Windows

This guide will help you set up and run the Notion-style Block Editor on Windows with local PostgreSQL.

## Prerequisites ✓

- ✓ Python 3.11+ installed
- ✓ PostgreSQL installed locally (user: postgres, password: SIQ3PAGDL8pa)
- ✓ Git (optional)

## Step-by-Step Setup

### 1. Install Dependencies

Open Command Prompt or PowerShell in the project directory:

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Setup Database

The `.env` file is already configured with your PostgreSQL credentials.

Create the database:

```cmd
python setup_database.py
```

This will:
- Connect to your PostgreSQL server
- Create the `notion_db` database
- Test the connection

### 3. Run Database Migrations

```cmd
alembic upgrade head
```

This creates all necessary tables (users, documents, blocks, revisions, etc.)

### 4. Start the Server

```cmd
python run.py
```

The API will be available at: http://localhost:8000

Interactive docs at: http://localhost:8000/docs

### 5. Test the Installation

Open a new terminal window and run the example:

```cmd
.venv\Scripts\activate
python example.py
```

Or use the CLI:

```cmd
python -m client.cli register alice alice@example.com
python -m client.cli login alice
python -m client.cli create "My First Document"
python -m client.cli list
```

## Common Commands

### Server Management

```cmd
# Start server
python run.py

# Stop server
Ctrl+C
```

### Database Management

```cmd
# Check migration status
alembic current

# View migration history
alembic history

# Create new migration (after model changes)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Reset database (WARNING: deletes all data)
python setup_database.py
alembic upgrade head
```

### Client Usage

```cmd
# Activate virtual environment first
.venv\Scripts\activate

# Register
python -m client.cli register <username> <email>

# Login
python -m client.cli login <username>

# Create document
python -m client.cli create "Document Title"

# List documents
python -m client.cli list

# Add content
python -m client.cli add <doc_id> "Some text" --type paragraph

# View blocks
python -m client.cli blocks <doc_id>

# Search
python -m client.cli search "query"

# Export
python -m client.cli export <doc_id> -o output.md

# Import
python -m client.cli import "Title" input.md
```

## Troubleshooting

### PostgreSQL Connection Issues

**Error: "could not connect to server"**

1. Check PostgreSQL is running:
   - Open Services (Win+R, type `services.msc`)
   - Look for "postgresql-x64-XX" service
   - Start if not running

2. Verify credentials in `.env` file

3. Test connection manually:
   ```cmd
   psql -U postgres -h localhost
   # Enter password: SIQ3PAGDL8pa
   ```

### Module Import Errors

**Error: "No module named 'fastapi'"**

Make sure virtual environment is activated:
```cmd
.venv\Scripts\activate
pip install -r requirements.txt
```

### Port Already in Use

**Error: "Address already in use"**

Another application is using port 8000. Change port in `run.py`:
```python
uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
```

### Database Migration Errors

**Error: "Target database is not up to date"**

Run migrations:
```cmd
alembic upgrade head
```

**Error: "Can't locate revision"**

Reset migrations (WARNING: deletes data):
```cmd
python setup_database.py
alembic upgrade head
```

## Project Structure

```
apiProject1/
├── app/                    # Backend application
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic
│   ├── models.py          # Database models
│   ├── schemas.py         # Pydantic schemas
│   ├── auth.py            # Authentication
│   └── main.py            # FastAPI app
├── client/                # Python client
│   ├── api_client.py      # API client class
│   └── cli.py             # CLI tool
├── alembic/               # Database migrations
├── .env                   # Environment config
├── requirements.txt       # Dependencies
├── run.py                 # Server startup
├── setup_database.py      # Database setup
└── example.py             # Usage example
```

## API Endpoints

All endpoints documented at: http://localhost:8000/docs

Key endpoints:
- `POST /auth/register` - Register user
- `POST /auth/login` - Login
- `POST /documents` - Create document
- `GET /documents` - List documents
- `POST /documents/{id}/commit` - Commit changes
- `GET /documents/{id}/blocks/root` - Get blocks
- `GET /search` - Search
- `GET /documents/{id}/export` - Export to Markdown

## Configuration

Edit `.env` to change settings:

```env
DATABASE_URL=postgresql://postgres:SIQ3PAGDL8pa@localhost:5432/notion_db
SECRET_KEY=<your-secret-key>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Next Steps

1. **Try the example**: `python example.py`
2. **Explore API docs**: http://localhost:8000/docs
3. **Read full docs**: See `README.md` and `SETUP.md`
4. **Build a frontend**: Connect to the REST API
5. **Customize**: Add new block types or features

## Getting Help

- Check server logs in the terminal
- View API documentation at `/docs`
- Review error messages carefully
- Ensure PostgreSQL is running
- Verify `.env` configuration

## Security Notes

⚠️ **Important for Production:**
- Change the `SECRET_KEY` in `.env`
- Use strong passwords
- Enable HTTPS
- Restrict database access
- Set up proper backups

For development, current settings are fine.

---

**Happy Coding! 🚀**

For more details, see `README.md` and `SETUP.md`

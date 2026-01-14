# Notion-Style Block Editor

A backend system for a Notion-style Markdown block editor with Python + FastAPI + PostgreSQL.

**Environment:** Python 3.11 | Windows | Local PostgreSQL

## Features

- **Block-based editing**: Documents composed of hierarchical blocks (paragraph, heading, list, todo, code, quote, divider)
- **Version control**: Full revision history with diff and restore capabilities
- **Offline support**: Multi-device sync with conflict detection and merge
- **Collaboration**: Document sharing with role-based access control (owner, editor, viewer)
- **Search**: Full-text search across blocks
- **Import/Export**: Markdown import and export
- **REST API**: Complete RESTful API
- **Python Client**: CLI and programmatic client

## Architecture

### Core Concepts

- **Blocks**: Basic content units with type, text, and properties
- **Operations**: All edits are tracked as operations (insert, delete, move, update)
- **Revisions**: Each commit creates a new revision with incremental version number
- **Devices**: Each client device has a unique ID for offline sync
- **Conflict detection**: Server detects and reports conflicts on commit

### Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy
- **Database**: PostgreSQL (local Windows installation)
- **Auth**: JWT tokens with bcrypt
- **Migrations**: Alembic
- **Client**: Python with requests

## Quick Start

### Prerequisites

- Python 3.11
- PostgreSQL installed locally on Windows
- Git (optional)

### Installation

**1. Clone the repository:**
```cmd
git clone <repo-url>
cd apiProject1
```

**2. Create virtual environment:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**3. Install dependencies:**
```cmd
pip install -r requirements.txt
```

**4. Configure environment:**

The `.env` file should already be configured. If not, copy from example:
```cmd
copy .env.example .env
```

Edit `.env` with your PostgreSQL credentials:
```env
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/notion_db
SECRET_KEY=<generate-secure-key>
```

**5. Setup database:**
```cmd
python setup_database.py
```

**6. Run migrations:**
```cmd
python -m alembic upgrade head
```

**7. Start the server:**
```cmd
python run.py
```

The API will be available at: http://localhost:8000

Interactive docs at: http://localhost:8000/docs

## Testing the Installation

### Option 1: Run the Example Script

```cmd
python example.py
```

This creates a demo user, document, and demonstrates all features.

### Option 2: Use the CLI

```cmd
# Register and login
python -m client.cli register alice alice@example.com
python -m client.cli login alice

# Create document
python -m client.cli create "My First Document"

# List documents
python -m client.cli list

# Add content (use document ID from list)
python -m client.cli add <doc_id> "Hello World!"

# View blocks
python -m client.cli blocks <doc_id>
```

### Option 3: Use the API Directly

Visit http://localhost:8000/docs for interactive API documentation.

## API Usage

### Authentication

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "password123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123"}'

# Returns: {"access_token": "...", "token_type": "bearer"}
```

### Documents

```bash
# Create document
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Process"}'

# List documents
curl http://localhost:8000/documents \
  -H "Authorization: Bearer <token>"

# Get document
curl http://localhost:8000/documents/{process_id} \
  -H "Authorization: Bearer <token>"
```

### Blocks

```bash
# Get root blocks
curl http://localhost:8000/documents/{process_id}/blocks/root \
  -H "Authorization: Bearer <token>"

# Commit changes
curl -X POST http://localhost:8000/documents/{process_id}/commit \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "...",
    "base_rev_number": 0,
    "client_batch_id": "...",
    "ops": [
      {
        "op_type": "insert_block",
        "data": {
          "block_id": "...",
          "parent_block_id": null,
          "order_key": "...",
          "block_type": "paragraph",
          "text": "Hello world",
          "props": {}
        }
      }
    ]
  }'
```

## Python Client

### CLI Usage

```cmd
# Authentication
python -m client.cli register <username> <email>
python -m client.cli login <username>
python -m client.cli me

# Documents
python -m client.cli create "Document Title"
python -m client.cli list
python -m client.cli get <doc_id>
python -m client.cli update <doc_id> "New Title"
python -m client.cli delete <doc_id>
python -m client.cli restore <doc_id>

# Blocks
python -m client.cli blocks <doc_id>
python -m client.cli add <doc_id> "Text" --type paragraph
python -m client.cli edit <doc_id> <block_id> "New text"
python -m client.cli delete-block <doc_id> <block_id>

# Revisions
python -m client.cli revisions <doc_id>
python -m client.cli restore-rev <doc_id> <rev_number>
python -m client.cli diff <doc_id> <from_rev> <to_rev>

# Search
python -m client.cli search "query"
python -m client.cli search-doc <doc_id> "query"

# Import/Export
python -m client.cli export <doc_id> -o output.md
python -m client.cli import "Title" input.md

# Sharing
python -m client.cli invite <doc_id> <email> --role editor
python -m client.cli share <doc_id> --expires 7
```

### Programmatic Usage

```python
from client.api_client import NotionClient

# Initialize client
client = NotionClient("http://localhost:8000")

# Login
client.login("alice", "password123")

# Create document
doc = client.create_document("My Process")
doc_id = doc["process_id"]

# Insert a block
result = client.insert_block(
    doc_id,
    base_rev=0,
    text="Hello world",
    block_type="paragraph"
)

# List blocks
blocks = client.get_root_blocks(doc_id)

# Search
results = client.search("hello")

# Export
markdown = client.export_document(doc_id)
```

## API Endpoints

### Auth
- `POST /auth/register` - Register user
- `POST /auth/login` - Login
- `GET /auth/me` - Get current user

### Documents
- `POST /documents` - Create document
- `GET /documents` - List documents
- `GET /documents/{id}` - Get document
- `PATCH /documents/{id}` - Update document
- `DELETE /documents/{id}` - Delete (soft) document
- `POST /documents/{id}/restore` - Restore document

### Blocks
- `GET /documents/{id}/blocks/root` - Get root blocks
- `GET /blocks/{id}/children` - Get child blocks
- `POST /documents/{id}/commit` - Commit operations

### Revisions
- `GET /documents/{id}/revisions` - List revisions
- `POST /documents/{id}/revisions/{rev}/restore` - Restore revision
- `GET /documents/{id}/revisions/diff` - Get diff

### Sharing
- `POST /documents/{id}/invites` - Invite user
- `GET /documents/{id}/acl` - Get ACL
- `DELETE /documents/{id}/acl/{user_id}` - Revoke access
- `POST /documents/{id}/share-links` - Create share link
- `GET /share/{token}` - Access shared document

### Search
- `GET /search` - Search all documents
- `GET /documents/{id}/search` - Search in document

### Import/Export
- `GET /documents/{id}/export` - Export to Markdown
- `POST /documents/import` - Import from Markdown

## Block Types

- `paragraph` - Regular text
- `heading1` - Level 1 heading
- `heading2` - Level 2 heading
- `list` - List item
- `todo` - Todo checkbox (props: `{checked: bool}`)
- `code` - Code block (props: `{language: str}`)
- `quote` - Blockquote
- `divider` - Horizontal rule

## Operation Types

- `insert_block` - Create new block
- `delete_block` - Delete block
- `move_block` - Move block (change parent/order)
- `update_text` - Update block text
- `update_props` - Update block properties

## Conflict Resolution

When committing with `base_rev_number < current_rev_number`:

1. Server checks for conflicts
2. Non-overlapping changes auto-merge
3. Conflicting changes return conflict details
4. Client must resolve and resubmit

## Database Schema

- `users` - User accounts
- `devices` - Client devices
- `documents` - Documents
- `document_acl` - Access control
- `share_links` - Public share links
- `blocks` - Current block state
- `revisions` - Revision history
- `ops` - Operations per revision
- `revision_snapshots` - Optional snapshots

## Development

### Database Management

```cmd
# Check migration status
python -m alembic current

# View migration history
python -m alembic history

# Create new migration (after model changes)
python -m alembic revision --autogenerate -m "description"

# Apply migrations
python -m alembic upgrade head

# Rollback one migration
python -m alembic downgrade -1

# Reset database (WARNING: deletes all data)
python setup_database.py
python -m alembic upgrade head
```

### Project Structure

```
apiProject1/
├── app/                    # Backend application
│   ├── routers/           # API endpoints
│   │   ├── auth.py
│   │   ├── documents.py
│   │   ├── blocks.py
│   │   ├── revisions.py
│   │   ├── sharing.py
│   │   ├── search.py
│   │   └── import_export.py
│   ├── services/          # Business logic
│   │   ├── block_service.py
│   │   ├── commit_service.py
│   │   ├── search_service.py
│   │   └── import_export_service.py
│   ├── models.py          # Database models
│   ├── schemas.py         # Pydantic schemas
│   ├── auth.py            # Authentication
│   ├── config.py          # Configuration
│   ├── database.py        # Database connection
│   └── main.py            # FastAPI app
├── client/                # Python client
│   ├── api_client.py      # API client class
│   └── cli.py             # CLI tool
├── alembic/               # Database migrations
│   ├── versions/          # Migration files
│   ├── env.py             # Alembic config
│   └── script.py.mako     # Migration template
├── .env                   # Environment config (not in git)
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── requirements.txt       # Python dependencies
├── alembic.ini            # Alembic configuration
├── run.py                 # Server startup
├── setup_database.py      # Database setup script
├── example.py             # Usage example
├── README.md              # This file
├── START_HERE.md          # Quick start guide
├── SETUP.md               # Detailed setup guide
└── QUICKSTART_WINDOWS.md  # Windows-specific guide
```

## Configuration

Edit `.env` to change settings:

```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/notion_db
SECRET_KEY=<your-secret-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Generate a secure secret key:
```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Troubleshooting

### PostgreSQL Connection Issues

**Error: "could not connect to server"**

1. Check PostgreSQL is running:
   - Open Services (Win+R, type `services.msc`)
   - Look for "postgresql-x64-XX" service
   - Start if not running

2. Verify credentials in `.env` file

3. Test connection:
   ```cmd
   psql -U postgres -h localhost
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

Change port in `run.py`:
```python
uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
```

### Database Migration Errors

**Error: "Target database is not up to date"**

Run migrations:
```cmd
python -m alembic upgrade head
```

**Error: "Can't locate revision"**

Reset migrations (WARNING: deletes data):
```cmd
python setup_database.py
python -m alembic upgrade head
```

## Security Notes

⚠️ **Important for Production:**

- Change the `SECRET_KEY` in `.env` to a secure random value
- Use strong passwords for all accounts
- Enable HTTPS with a reverse proxy (nginx, Apache)
- Restrict database access to localhost or use firewall rules
- Set up proper backups and monitoring
- Review and configure CORS settings in `app/main.py`
- Use environment variables instead of `.env` file in production
- Enable rate limiting for API endpoints
- Regular security updates for all dependencies

For development, current settings are acceptable.

## Next Steps

1. **Try the example**: `python example.py`
2. **Explore API docs**: http://localhost:8000/docs
3. **Read detailed guides**:
   - `START_HERE.md` - Quick reference
   - `QUICKSTART_WINDOWS.md` - Windows-specific setup
   - `SETUP.md` - Advanced configuration
4. **Build a frontend**: Connect to the REST API with React, Vue, or any framework
5. **Customize**: Add new block types, features, or integrations

## Requirements

- Python 3.11
- PostgreSQL 13+ (local Windows installation)
- Windows OS
- 100MB+ disk space

## License

MIT

## Contributing

Contributions welcome! Please submit pull requests or issues.

## Support

- Check `START_HERE.md` for quick start
- See `QUICKSTART_WINDOWS.md` for Windows-specific help
- Review `SETUP.md` for detailed setup
- Check server logs for error messages
- Verify PostgreSQL is running
- Review `.env` configuration

---

**Built with FastAPI, SQLAlchemy, and PostgreSQL**

For questions or issues, please open a GitHub issue.

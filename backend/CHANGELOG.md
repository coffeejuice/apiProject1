# Changelog

## [Updated for Python 3.11] - 2026-01-12

### Changed
- **Python Version**: Updated to Python 3.11 (from 3.13)
- **Requirements**: Updated all dependencies for Python 3.11 compatibility
  - pydantic: 2.10.7
  - pydantic-core: 2.27.2
  - sqlalchemy: 2.0.45
  - psycopg[binary]: 3.2.3
- **Documentation**: Updated all docs to reflect Python 3.11 environment
- **README.md**: Completely rewritten for local Windows setup
- **SETUP.md**: Removed Docker references, focused on local PostgreSQL
- **Environment**: Configured for Windows + local PostgreSQL

### Removed
- **Docker Support**: Removed Docker and Docker Compose files
  - Deleted: `docker-compose.yml`
  - Deleted: `Dockerfile`
- **Docker Documentation**: Removed all Docker-related instructions

### Fixed
- Database connection string format (postgresql+psycopg://)
- Python 3.11 compatibility issues
- Windows-specific installation instructions

### Environment
- **OS**: Windows
- **Python**: 3.11
- **Database**: PostgreSQL (local installation)
- **Database Credentials**:
  - User: postgres
  - Password: SIQ3PAGDL8pa
  - Database: notion_db

### Installation
Current setup uses:
1. Local PostgreSQL on Windows
2. Python 3.11 virtual environment
3. pip for dependency management
4. Alembic for database migrations

### Documentation
Updated files:
- ✅ README.md - Complete rewrite for Python 3.11 + Windows
- ✅ SETUP.md - Removed Docker, added Windows-specific setup
- ✅ QUICKSTART_WINDOWS.md - Already Windows-focused
- ✅ START_HERE.md - Quick reference guide
- ✅ requirements.txt - Python 3.11 compatible versions

### Migration from Python 3.13

If upgrading from Python 3.13 installation:

1. Remove old virtual environment:
   ```cmd
   rmdir /s .venv
   ```

2. Create new Python 3.11 virtual environment:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

4. Database should work as-is (no changes needed)

### Notes
- All core functionality remains unchanged
- API endpoints are identical
- Database schema is compatible
- Client code works without modification
- Only deployment method changed (Docker → Local)

## [Initial Release] - 2026-01-12

### Added
- FastAPI backend with REST API
- PostgreSQL database with SQLAlchemy ORM
- Block-based document editing
- Version control and revision history
- Multi-device offline sync
- Conflict detection and merge
- Role-based access control (owner, editor, viewer)
- Public share links
- Full-text search
- Markdown import/export
- Python CLI client
- Programmatic API client
- JWT authentication
- Database migrations with Alembic
- Complete documentation

### Features
- 8 block types: paragraph, heading1, heading2, list, todo, code, quote, divider
- 5 operation types: insert, delete, move, update_text, update_props
- Hierarchical block structure
- Idempotent commits
- Device-based sync
- Automatic conflict resolution for non-overlapping changes

### API Endpoints
- Authentication (register, login, me)
- Documents (CRUD, restore, list)
- Blocks (read, commit operations)
- Revisions (list, restore, diff)
- Sharing (invites, ACL, share links)
- Search (global, per-document)
- Import/Export (Markdown)

### Database Schema
- 11 tables: users, devices, documents, blocks, revisions, ops, document_acl, share_links, revision_snapshots
- Proper indexes for performance
- Foreign key constraints
- Soft delete support

### Client Tools
- CLI with 20+ commands
- Programmatic Python client
- Offline queue support
- Device ID management
- Config persistence

# Changelog

Note: This file is historical. For current rules, see .aiassistant/rules/.

## [Updated for Python 3.11] - 2026-01-12

### Changed
- Python updated to 3.11 (from 3.13).
- Dependencies updated for Python 3.11 compatibility:
  - pydantic 2.10.7
  - pydantic-core 2.27.2
  - sqlalchemy 2.0.45
  - psycopg[binary] 3.2.3
- Documentation updated for Windows + local PostgreSQL.
- README.md rewritten for local setup.
- SETUP.md updated for Windows.
- Docker support removed.

### Removed
- Docker and Docker Compose files and instructions.

### Fixed
- Database connection string format (postgresql+psycopg://).
- Windows-specific installation instructions.

### Environment
- OS: Windows
- Python: 3.11
- Database: PostgreSQL (local)

### Notes
- API endpoints unchanged.
- Database schema compatible; no changes required.

## [Initial Release] - 2026-01-12

### Added
- FastAPI backend with REST API.
- PostgreSQL database with SQLAlchemy ORM.
- Block-based document editing.
- Revision history and conflict handling.
- Role-based access control and share links.
- Full-text search and Markdown import/export.
- Python CLI client and API client.
- JWT authentication.
- Alembic migrations.
- Documentation.

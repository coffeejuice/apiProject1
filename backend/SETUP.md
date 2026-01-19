# Setup Guide

## Prerequisites

- Python 3.11
- PostgreSQL 13+ (local Windows installation)
- Windows OS

## Installation

### 1. Install PostgreSQL

Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/)

During installation, remember your:
- Username (default: `postgres`)
- Password
- Port (default: `5432`)

### 2. Clone Repository

```cmd
git clone <repo>
cd apiProject1
```

### 3. Setup Python Environment

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example configuration:
```cmd
copy .env.example .env
```

Edit `.env` with your PostgreSQL credentials:
```env
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/notion_db
SECRET_KEY=your-secret-key-generate-random-string
```

Generate a secure secret key:
```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Create Database

```cmd
python setup_database.py
```

This will:
- Connect to PostgreSQL
- Create the `notion_db` database
- Test the connection

### 6. Run Migrations

```cmd
python -m alembic upgrade head
```

This creates all necessary tables.

### 7. Start Server

```cmd
python run.py
```

The API will be available at: http://localhost:8000

API docs at: http://localhost:8000/docs

### 8. Test Installation

```cmd
curl http://localhost:8000/health
```

Or run the example:
```cmd
python example.py
```

## First Steps

### 1. Register a User

```cmd
python -m client.cli register alice alice@example.com
# Enter password when prompted
```

### 2. Login

```cmd
python -m client.cli login alice
# Enter password when prompted
```

### 3. Create a Document

```cmd
python -m client.cli create "My First Document"
```

### 4. View Documents

```cmd
python -m client.cli list
```

### 5. Add Content

```cmd
# Use document ID from previous command
python -m client.cli add <document_id> "Hello, World!"
```

### 6. View Blocks

```cmd
python -m client.cli blocks <document_id>
```

## Configuration Options

### Environment Variables

Required variables in `.env`:

- `DATABASE_URL` - PostgreSQL connection string
  - Format: `postgresql+psycopg://username:password@host:port/database`
  - Example: `postgresql+psycopg://postgres:mypass@localhost:5432/notion_db`

- `SECRET_KEY` - JWT secret key (use strong random string)
  - Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

- `ALGORITHM` - JWT algorithm (default: HS256)

- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiry (default: 30)

### PostgreSQL Configuration

Default PostgreSQL settings:
- Host: `localhost`
- Port: `5432`
- Database: `notion_db`
- User: `postgres`

To change these, update the `DATABASE_URL` in `.env`

## Database Migrations

### View Current Migration

```cmd
python -m alembic current
```

### View Migration History

```cmd
python -m alembic history
```

### Create New Migration

After modifying models in `app/models.py`:

```cmd
python -m alembic revision --autogenerate -m "description"
```

### Apply Migrations

```cmd
python -m alembic upgrade head
```

### Rollback Migration

```cmd
python -m alembic downgrade -1
```

### Reset Database

⚠️ **WARNING: This deletes all data!**

```cmd
python setup_database.py
python -m alembic upgrade head
```

## Troubleshooting

### PostgreSQL Connection Errors

**Error: "could not connect to server"**

1. Check PostgreSQL service is running:
   - Press `Win + R`, type `services.msc`
   - Find "postgresql-x64-XX" service
   - Make sure it's "Running"

2. Verify credentials in `.env`:
   ```cmd
   type .env
   ```

3. Test PostgreSQL connection:
   ```cmd
   psql -U postgres -h localhost
   # Enter your password
   ```

4. Check PostgreSQL logs:
   - Location: `C:\Program Files\PostgreSQL\XX\data\log\`

**Error: "password authentication failed"**

- Double-check password in `.env`
- Ensure no extra spaces in connection string
- Try resetting PostgreSQL password

### Database Setup Errors

**Error: "database already exists"**

Database was created previously. To recreate:
```cmd
python setup_database.py
# Select 'y' when prompted to drop and recreate
```

**Error: "permission denied to create database"**

User doesn't have permission. Use superuser account or grant permissions:
```sql
ALTER USER postgres CREATEDB;
```

### Migration Errors

**Error: "Can't locate revision"**

Reset migrations:
```cmd
# Backup your data first!
python setup_database.py
python -m alembic upgrade head
```

**Error: "Target database is not up to date"**

Apply pending migrations:
```cmd
python -m alembic upgrade head
```

### Import Errors

**Error: "No module named 'fastapi'"**

Virtual environment not activated or packages not installed:
```cmd
.venv\Scripts\activate
pip install -r requirements.txt
```

**Error: "No module named 'app'"**

Make sure you're in the project root directory:
```cmd
cd C:\Users\...\apiProject1
.venv\Scripts\activate
python run.py
```

### Port Already in Use

**Error: "Address already in use"**

Another application is using port 8000.

Option 1: Stop the other application

Option 2: Change port in `run.py`:
```python
uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
```

### Server Won't Start

Check for errors in console output.

Common issues:
1. `.env` file missing or misconfigured
2. Database not created
3. Migrations not applied
4. Port already in use
5. Dependencies not installed

## Production Deployment

### Security Checklist

- [ ] Generate strong `SECRET_KEY`
- [ ] Use HTTPS (reverse proxy)
- [ ] Set secure database password
- [ ] Restrict database access
- [ ] Configure CORS properly in `app/main.py`
- [ ] Use environment variables (not `.env` file)
- [ ] Enable rate limiting
- [ ] Set up monitoring and logging
- [ ] Configure automated backups
- [ ] Regular security updates

### Recommended Production Stack

- **Application Server**: Gunicorn with Uvicorn workers
- **Reverse Proxy**: Nginx or Apache
- **Database**: PostgreSQL with replication
- **OS**: Windows Server or Linux
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK stack or similar

### Production Command

```cmd
gunicorn app.main:app ^
  --workers 4 ^
  --worker-class uvicorn.workers.UvicornWorker ^
  --bind 0.0.0.0:8000 ^
  --access-logfile - ^
  --error-logfile -
```

Note: Install gunicorn first: `pip install gunicorn`

### Environment Variables

In production, use system environment variables instead of `.env`:

```cmd
set DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
set SECRET_KEY=your-production-secret
python run.py
```

Or configure in Windows Environment Variables:
- Settings → System → About → Advanced system settings → Environment Variables

## Testing

### Manual API Testing

Use the interactive docs:
http://localhost:8000/docs

### CLI Testing

Run through basic workflow:
```cmd
python -m client.cli register testuser test@example.com
python -m client.cli login testuser
python -m client.cli create "Test Doc"
python -m client.cli list
python -m client.cli add <doc_id> "Test content"
python -m client.cli blocks <doc_id>
python -m client.cli search "Test"
```

### Automated Testing

Add tests using pytest (not included):
```cmd
pip install pytest pytest-asyncio httpx
pytest tests/
```

### Load Testing

Use tools like:
- Apache Bench: `ab -n 1000 -c 10 http://localhost:8000/`
- Locust: Python-based load testing
- K6: Modern load testing tool

## Maintenance

### Database Backup

```cmd
pg_dump -U postgres -h localhost notion_db > backup.sql
```

### Database Restore

```cmd
psql -U postgres -h localhost notion_db < backup.sql
```

### Log Rotation

Configure log rotation in production to prevent disk space issues.

### Monitoring

Monitor:
- API response times
- Database connections
- Disk space
- Memory usage
- Error rates

### Updates

Regular updates:
```cmd
pip install --upgrade -r requirements.txt
python -m alembic upgrade head
```

## Support

- Check logs for error messages
- Verify PostgreSQL is running
- Review `.env` configuration
- Test database connection
- Check firewall settings
- See README.md for more info
- Check QUICKSTART_WINDOWS.md for Windows-specific help

## Next Steps

- Read README.md for full documentation
- Try example.py for a demo
- Explore API docs at /docs
- Build a frontend
- Customize for your needs

---

For detailed Windows setup, see `QUICKSTART_WINDOWS.md`

For API documentation, see `README.md`

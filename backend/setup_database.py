#!/usr/bin/env python3
"""
Database setup script for Windows
Creates the notion_db database if it doesn't exist
"""
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg import sql
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

# Parse DATABASE_URL from .env
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("✗ DATABASE_URL not found in .env file")
    sys.exit(1)

parsed = urlparse(database_url)
PG_USER = parsed.username or "postgres"
PG_PASSWORD = parsed.password or ""
PG_HOST = parsed.hostname or "localhost"
PG_PORT = parsed.port or 5432
DB_NAME = parsed.path.lstrip('/') or "notion_db"

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def quote_ident(identifier):
    if IDENTIFIER_RE.match(identifier):
        return identifier
    return '"' + identifier.replace('"', '""') + '"'

def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"

def run_psql_as_postgres(sql_statement, dbname="postgres"):
    cmd = [
        "sudo",
        "-n",
        "-u",
        "postgres",
        "psql",
        "-d",
        dbname,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql_statement,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_output = (result.stderr or result.stdout or "").strip()
        print(f"\n✗ Unable to run psql as postgres: {error_output}")
        print("Ensure 'sudo -u postgres psql' works or set valid admin credentials.")
        return False
    return True

def build_conninfo(user, password, host, port, dbname):
    parts = [f"user={user}"]
    if password:
        parts.append(f"password={password}")
    if host:
        parts.append(f"host={host}")
    if port:
        parts.append(f"port={port}")
    if dbname:
        parts.append(f"dbname={dbname}")
    return " ".join(parts)

def parse_admin_url(admin_url):
    parsed_admin = urlparse(admin_url)
    admin_user = parsed_admin.username or "postgres"
    admin_password = parsed_admin.password or ""
    admin_host = parsed_admin.hostname or PG_HOST
    admin_port = parsed_admin.port or PG_PORT
    admin_db = parsed_admin.path.lstrip('/') or "postgres"
    return admin_user, admin_password, admin_host, admin_port, admin_db

def get_admin_config():
    admin_url = os.getenv("DB_ADMIN_URL")
    if admin_url:
        return parse_admin_url(admin_url)

    admin_user = os.getenv("DB_ADMIN_USER")
    if admin_user:
        admin_password = os.getenv("DB_ADMIN_PASSWORD", "")
        admin_host = os.getenv("DB_ADMIN_HOST", PG_HOST)
        admin_port = os.getenv("DB_ADMIN_PORT")
        admin_port = int(admin_port) if admin_port else PG_PORT
        admin_db = os.getenv("DB_ADMIN_DB", "postgres")
        return admin_user, admin_password, admin_host, admin_port, admin_db

    return None

def prompt_admin_config():
    if not sys.stdin.isatty():
        return None

    admin_user = input("PostgreSQL admin user [postgres]: ").strip() or "postgres"
    admin_password = getpass.getpass(f"Password for {admin_user}: ")
    return admin_user, admin_password, PG_HOST, PG_PORT, "postgres"

def resolve_admin_config():
    admin_config = get_admin_config()
    if admin_config:
        return admin_config
    return prompt_admin_config()

def ensure_role_via_psql(role_name, role_password):
    if not role_name:
        return False

    role_ident = quote_ident(role_name)
    role_literal = sql_literal(role_name)
    password_literal = sql_literal(role_password)
    sql_statement = (
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN "
        f"CREATE ROLE {role_ident} WITH LOGIN PASSWORD {password_literal}; "
        "ELSE "
        f"ALTER ROLE {role_ident} WITH LOGIN PASSWORD {password_literal}; "
        "END IF; END $$;"
    )
    return run_psql_as_postgres(sql_statement)

def ensure_postgres_password(admin_config):
    """Ensure postgres role password matches the admin password in .env."""
    if not admin_config:
        return True

    admin_user, admin_password, admin_host, admin_port, admin_db = admin_config
    if admin_user != "postgres" or not admin_password:
        return True

    admin_conninfo = build_conninfo(admin_user, admin_password, admin_host, admin_port, admin_db)

    try:
        print("\nSetting password for role 'postgres'...")
        conn = psycopg.connect(admin_conninfo, autocommit=True)
        cursor = conn.cursor()
        cursor.execute(
            sql.SQL("ALTER ROLE postgres WITH PASSWORD {}").format(
                sql.Literal(admin_password)
            )
        )
        cursor.close()
        conn.close()
        print("✓ Postgres password ensured.")
        return True
    except psycopg.OperationalError as e:
        print(f"\n✗ Failed to connect as postgres: {e}")
        print("Attempting to update password via local postgres superuser...")
        if run_psql_as_postgres(
            f"ALTER ROLE postgres WITH PASSWORD {sql_literal(admin_password)};"
        ):
            print("✓ Postgres password ensured.")
            return True
        return False
    except Exception as e:
        print(f"\n✗ Failed to set postgres password: {e}")
        return False

def can_connect_as_app():
    conninfo = build_conninfo(PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, "postgres")
    try:
        conn = psycopg.connect(conninfo)
        conn.close()
        return True
    except psycopg.OperationalError as e:
        print(f"\n✗ App user connection failed: {e}")
        return False

def ensure_role(admin_config):
    """Ensure the application role exists and matches the password in DATABASE_URL."""
    admin_user, admin_password, admin_host, admin_port, admin_db = admin_config
    admin_conninfo = build_conninfo(admin_user, admin_password, admin_host, admin_port, admin_db)

    try:
        conn = psycopg.connect(admin_conninfo, autocommit=True)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (PG_USER,))
        exists = cursor.fetchone()

        if exists:
            print(f"Updating password for role '{PG_USER}'...")
            cursor.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(PG_USER),
                    sql.Literal(PG_PASSWORD),
                )
            )
        else:
            print(f"Creating role '{PG_USER}'...")
            cursor.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(PG_USER),
                    sql.Literal(PG_PASSWORD),
                )
            )

        cursor.close()
        conn.close()
        return True
    except psycopg.OperationalError as e:
        print(f"\n✗ Failed to connect as admin: {e}")
        print("Attempting to create/update role via local postgres superuser...")
        if ensure_role_via_psql(PG_USER, PG_PASSWORD):
            print(f"✓ Role '{PG_USER}' ensured via local postgres.")
            return True
        print(f"\n✗ Failed to create/update role '{PG_USER}'.")
        return False
    except Exception as e:
        print(f"\n✗ Failed to create/update role '{PG_USER}': {e}")
        return False

def create_database_with_conninfo(conninfo, owner=None):
    conn = psycopg.connect(conninfo, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    exists = cursor.fetchone()

    recreate = False
    if exists:
        print(f"Database '{DB_NAME}' already exists.")
        response = input("Do you want to drop and recreate it? (y/N): ")
        if response.lower() == 'y':
            print(f"Dropping database '{DB_NAME}'...")
            cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(DB_NAME)))
            print("✓ Database dropped")
            recreate = True
        else:
            print("Using existing database.")
            cursor.close()
            conn.close()
            return True

    if not exists or recreate:
        print(f"Creating database '{DB_NAME}'...")
        if owner:
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DB_NAME),
                    sql.Identifier(owner),
                )
            )
        else:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f"✓ Database '{DB_NAME}' created successfully!")

    cursor.close()
    conn.close()
    return True

def create_database(admin_config=None):
    """Create the notion_db database"""
    try:
        # Connect to default postgres database
        print(f"Connecting to PostgreSQL as {PG_USER}...")
        conninfo = build_conninfo(PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, "postgres")
        return create_database_with_conninfo(conninfo)
    except psycopg.OperationalError as e:
        if not admin_config:
            print(f"\n✗ Connection failed: {e}")
            print("\nPlease check:")
            print("1. PostgreSQL is running")
            print("2. Username and password are correct")
            print("3. PostgreSQL is listening on localhost:5432")
            return False

        admin_user, admin_password, admin_host, admin_port, admin_db = admin_config
        admin_conninfo = build_conninfo(admin_user, admin_password, admin_host, admin_port, admin_db)
        print(f"\nRetrying database creation as {admin_user}...")
        try:
            return create_database_with_conninfo(admin_conninfo, owner=PG_USER)
        except Exception as retry_error:
            print(f"\n✗ Error: {retry_error}")
            return False
    except Exception as e:
        if admin_config:
            admin_user, admin_password, admin_host, admin_port, admin_db = admin_config
            admin_conninfo = build_conninfo(admin_user, admin_password, admin_host, admin_port, admin_db)
            print(f"\nRetrying database creation as {admin_user}...")
            try:
                return create_database_with_conninfo(admin_conninfo, owner=PG_USER)
            except Exception as retry_error:
                print(f"\n✗ Error: {retry_error}")
                return False
        print(f"\n✗ Error: {e}")
        return False

def apply_grants(conninfo, use_for_role=False):
    conn = psycopg.connect(conninfo, autocommit=True)
    cursor = conn.cursor()

    cursor.execute(
        sql.SQL("GRANT CONNECT, CREATE, TEMPORARY ON DATABASE {} TO {}").format(
            sql.Identifier(DB_NAME),
            sql.Identifier(PG_USER),
        )
    )
    cursor.execute(
        sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
            sql.Identifier(PG_USER)
        )
    )
    cursor.execute(
        sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {}").format(
            sql.Identifier(PG_USER)
        )
    )
    cursor.execute(
        sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {}").format(
            sql.Identifier(PG_USER)
        )
    )
    cursor.execute(
        sql.SQL("GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {}").format(
            sql.Identifier(PG_USER)
        )
    )

    if use_for_role:
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON TABLES TO {}"
            ).format(sql.Identifier(PG_USER), sql.Identifier(PG_USER))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON SEQUENCES TO {}"
            ).format(sql.Identifier(PG_USER), sql.Identifier(PG_USER))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON FUNCTIONS TO {}"
            ).format(sql.Identifier(PG_USER), sql.Identifier(PG_USER))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT USAGE ON TYPES TO {}"
            ).format(sql.Identifier(PG_USER), sql.Identifier(PG_USER))
        )
    else:
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON TABLES TO {}"
            ).format(sql.Identifier(PG_USER))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON SEQUENCES TO {}"
            ).format(sql.Identifier(PG_USER))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT ALL PRIVILEGES ON FUNCTIONS TO {}"
            ).format(sql.Identifier(PG_USER))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT USAGE ON TYPES TO {}"
            ).format(sql.Identifier(PG_USER))
        )

    cursor.close()
    conn.close()

def grant_permissions(admin_config=None):
    """Grant database and schema permissions to the user from DATABASE_URL."""
    try:
        print(f"\nEnsuring privileges for '{PG_USER}' on '{DB_NAME}'...")
        app_conninfo = build_conninfo(PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, DB_NAME)
        apply_grants(app_conninfo, use_for_role=False)
        print("✓ Permissions ensured.")
        return True
    except psycopg.Error as e:
        if not admin_config:
            print(f"\n✗ Permission setup failed: {e}")
            print("Ensure the role can grant privileges or provide admin credentials.")
            return False

        admin_user, admin_password, admin_host, admin_port, _admin_db = admin_config
        admin_conninfo = build_conninfo(admin_user, admin_password, admin_host, admin_port, DB_NAME)
        print(f"\nRetrying grants as {admin_user}...")
        try:
            apply_grants(admin_conninfo, use_for_role=True)
            print("✓ Permissions ensured.")
            return True
        except Exception as retry_error:
            print(f"\n✗ Permission setup failed: {retry_error}")
            return False

def test_connection():
    """Test connection to the newly created database"""
    try:
        print(f"\nTesting connection to '{DB_NAME}'...")
        conn = psycopg.connect(
            build_conninfo(PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, DB_NAME)
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✓ Connected successfully!")
        print(f"PostgreSQL version: {version[0].split(',')[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("Notion-Style Block Editor - Database Setup")
    print("=" * 60)
    print()

    admin_config = get_admin_config()
    app_can_connect = can_connect_as_app()
    if not app_can_connect:
        if not admin_config:
            admin_config = resolve_admin_config()
        if not admin_config:
            print("\nProvide admin credentials via prompt or set DB_ADMIN_URL/DB_ADMIN_USER.")
            sys.exit(1)

    if admin_config and not ensure_postgres_password(admin_config):
        sys.exit(1)

    if not app_can_connect:
        if not ensure_role(admin_config):
            sys.exit(1)

    # Create database
    if not create_database(admin_config):
        sys.exit(1)

    # Grant privileges to the app user
    if not grant_permissions(admin_config):
        sys.exit(1)

    # Test connection
    if not test_connection():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Database setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run migrations: alembic upgrade head")
    print("2. Start the server: python run.py")
    print()

if __name__ == "__main__":
    main()

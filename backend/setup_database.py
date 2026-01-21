#!/usr/bin/env python3
"""
Database setup script for Windows
Creates the notion_db database if it doesn't exist
"""
import psycopg
from psycopg import sql
import sys
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

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

def create_database():
    """Create the notion_db database"""
    try:
        # Connect to default postgres database
        print(f"Connecting to PostgreSQL as {PG_USER}...")
        conn = psycopg.connect(
            f"user={PG_USER} password={PG_PASSWORD} host={PG_HOST} port={PG_PORT} dbname=postgres",
            autocommit=True
        )
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        exists = cursor.fetchone()

        if exists:
            print(f"Database '{DB_NAME}' already exists.")
            response = input("Do you want to drop and recreate it? (y/N): ")
            if response.lower() == 'y':
                print(f"Dropping database '{DB_NAME}'...")
                cursor.execute(sql.SQL("DROP DATABASE {}").format(
                    sql.Identifier(DB_NAME)
                ))
                print("✓ Database dropped")
            else:
                print("Using existing database.")
                cursor.close()
                conn.close()
                return True

        if not exists:
            print(f"Creating database '{DB_NAME}'...")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(DB_NAME)
            ))
            print(f"✓ Database '{DB_NAME}' created successfully!")

        cursor.close()
        conn.close()
        return True

    except psycopg.OperationalError as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nPlease check:")
        print("1. PostgreSQL is running")
        print("2. Username and password are correct")
        print("3. PostgreSQL is listening on localhost:5432")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_connection():
    """Test connection to the newly created database"""
    try:
        print(f"\nTesting connection to '{DB_NAME}'...")
        conn = psycopg.connect(
            f"user={PG_USER} password={PG_PASSWORD} host={PG_HOST} port={PG_PORT} dbname={DB_NAME}"
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

    # Create database
    if not create_database():
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

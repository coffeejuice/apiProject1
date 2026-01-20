"""Run database migration for system blocks"""
import sys
from pathlib import Path
from sqlalchemy import text
from app.database import engine

def run_migration(migration_file: str):
    """Run a SQL migration file"""
    migration_path = Path(__file__).parent / "migrations" / migration_file

    if not migration_path.exists():
        print(f"Error: Migration file not found: {migration_path}")
        sys.exit(1)

    print(f"Running migration: {migration_file}")

    with open(migration_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    try:
        with engine.begin() as conn:
            # Split by statement separator and execute each
            statements = [s.strip() for s in sql.split(';') if s.strip()]

            for i, statement in enumerate(statements, 1):
                if statement:
                    print(f"Executing statement {i}/{len(statements)}...")
                    conn.execute(text(statement))

        print("Migration completed successfully!")

    except Exception as e:
        print(f"Error running migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_file>")
        print("Example: python run_migration.py 002_add_system_blocks_safe.sql")
        sys.exit(1)

    migration_file = sys.argv[1]
    run_migration(migration_file)

import sys
from pathlib import Path

# Add the backend directory to sys.path to allow importing from app
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database import engine
from app.models.settings import Setting

def recreate_settings_table():
    print("Dropping settings table...")
    try:
        Setting.__table__.drop(engine)
        print("Settings table dropped.")
    except Exception as e:
        print(f"Error dropping table (it might not exist): {e}")

    print("Creating settings table...")
    Setting.__table__.create(engine)
    print("Settings table created successfully.")

if __name__ == "__main__":
    recreate_settings_table()

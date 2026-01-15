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

import os
import sys

# Add the project root to sys.path to allow importing from app
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text
from app.config import settings
from app.auth import get_password_hash

DATABASE_URL = str(settings.DATABASE_URL)

def init_db_raw():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Cleaning up database (dropping schema public)...")
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()
    
    print("Dropped and recreated public schema.")

    # Now use SQLAlchemy to create tables
    from app.database import Base
    import app.models # Ensure all models are loaded
    
    Base.metadata.create_all(bind=engine)
    print("Created all tables from models.")

    from sqlalchemy.orm import Session
    from app.models import User, Department, UiLanguageModel
    
    with Session(engine) as session:
        # Create default department and language
        dept = Department(department_id=1, department_name="Default")
        lang = UiLanguageModel(language_id=1, name="English")
        session.add(dept)
        session.add(lang)
        session.flush() # Get IDs if they are serial
        
        # Create demo_user
        password = "password123"
        hashed_password = get_password_hash(password)
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
            
        user = User(
            login="demo_user",
            email="demo@example.com",
            password_hashed=hashed_password,
            department_id=dept.department_id,
            language_id=lang.language_id,
            full_name="Demo User"
        )
        session.add(user)
        session.commit()
        print("Created demo_user with password123")

if __name__ == "__main__":
    init_db_raw()

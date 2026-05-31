from sqlalchemy import text, inspect
from app.database import engine

with engine.connect() as connection:
    inspector = inspect(engine)
    columns = inspector.get_columns('users')
    print(f"Columns in 'users' table:")
    for column in columns:
        print(f" - {column['name']}: {column['type']}")

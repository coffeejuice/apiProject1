from sqlalchemy import text, inspect
from app.database import engine

with engine.connect() as connection:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables in database: {tables}")

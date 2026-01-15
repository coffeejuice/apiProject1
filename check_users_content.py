from sqlalchemy import text
from app.database import engine

with engine.connect() as connection:
    result = connection.execute(text("SELECT * FROM users")).all()
    print(f"Users in 'users' table: {len(result)}")
    for row in result:
        print(row)

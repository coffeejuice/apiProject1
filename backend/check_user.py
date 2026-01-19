from sqlalchemy import text
from app.database import engine

with engine.connect() as connection:
    result = connection.execute(text("SELECT login, password_hashed FROM accounts WHERE login = 'demo_user'")).first()
    if result:
        login, password_hashed = result
        print(f"User found: {login}")
        # In psycopg, BYTEA comes back as bytes
        print(f"Hashed password (bytes): {password_hashed}")
        if isinstance(password_hashed, bytes):
            try:
                print(f"Hashed password (decoded): {password_hashed.decode('utf-8')}")
            except:
                print("Could not decode hash as utf-8")
        else:
            print(f"Hashed password is not bytes: {type(password_hashed)}")
    else:
        print("User 'demo_user' not found in database.")

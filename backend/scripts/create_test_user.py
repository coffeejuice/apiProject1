"""
Quick script to create a test user for the frontend
"""
from app.database import SessionLocal
from app.models.user import User
from app.auth import get_password_hash

def create_test_user():
    db = SessionLocal()

    # Check if user already exists
    existing = db.query(User).filter(User.login == "testuser").first()
    if existing:
        print(f"✓ User 'testuser' already exists (ID: {existing.user_id})")
        print(f"  Email: {existing.email}")
        return

    # Create new user
    user = User(
        login="testuser",
        email="test@example.com",
        password_hashed=get_password_hash("password123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"✓ Created test user:")
    print(f"  Username: testuser")
    print(f"  Password: password123")
    print(f"  Email: test@example.com")
    print(f"  User ID: {user.user_id}")

if __name__ == "__main__":
    create_test_user()

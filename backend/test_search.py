from app.database import SessionLocal
from app.models.document.process import Process
from app.models.user import User

db = SessionLocal()

# Get testuser
user = db.query(User).filter(User.login == "testuser").first()
if not user:
    print("User not found")
    exit(1)

# Create a test document
doc = Process(
    title="My Test Document",
    user_id=user.user_id
)
db.add(doc)
db.commit()
print(f"Created document: {doc.title} (ID: {doc.process_id})")

# Search for it
from app.services.search_service import search_blocks
results = search_blocks(db, user.user_id, "Test")
print(f"Search results: {len(results)} found")
for r in results:
    print(f"  - {r.snippet} (process_id: {r.process_id})")

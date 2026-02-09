from app.database import SessionLocal
from app.models.document.document import Document
from app.models.user import User

db = SessionLocal()

# Get testuser
user = db.query(User).filter(User.login == "testuser").first()
if not user:
    print("User not found")
    exit(1)

# Create a test document
doc = Document(
    title="My Test Document",
    user_id=user.user_id
)
db.add(doc)
db.commit()
print(f"Created document: {doc.title} (ID: {doc.document_id})")

# Search for it
from app.services.search_service import search_blocks
results = search_blocks(db, user.user_id, "Test")
print(f"Search results: {len(results)} found")
for r in results:
    print(f"  - {r.snippet} (document_id: {r.document_id})")

import sys
import os

# Ensure we can import app modules
# Moved to utils_to_delete, so we need to go up two levels to find 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.client import ApiClient

def seed():
    # Initialize API Client
    api = ApiClient("http://localhost:8001")
    
    print("Logging in...")
    if not api.login("demo_user", "password123"):
        print("Login failed! Please check if the server is running and credentials are correct.")
        return

    print("Login successful. Creating documents...")
    
    for i in range(1, 21):
        doc_title = f"Doc {i}"
        print(f"Creating {doc_title}...")
        res = api.create_document(doc_title)
        if res:
            print(f"  Success: {res}")
        else:
            print("  Failed.")

    print("Seeding complete.")

if __name__ == "__main__":
    seed()

#!/usr/bin/env python3
"""
Example usage of the Notion-style Block Editor API client
"""
from frontend_obsolete.client.api_client import NotionClient
import time

def main():
    # Initialize client
    client = NotionClient("http://localhost:8001")

    print("=== Notion-Style Block Editor Demo ===\n")

    is_logged = False
    is_new_user = False
    print("1. Logging in...")
    if client.login("demo_user", "password123"):
        is_logged = True
        print("Successfully logged in!")

    if not is_logged:
        print("Login failed! \n2. Try registering a new user...")
        # Register and login (comment out if already registered)
        client.register("demo_user", "demo@example.com", "password123")
        is_new_user = True

    if is_new_user:
        print("1. Logging in again...")
        if client.login("demo_user", "password123"):
            is_logged = True
            print("Successfully logged in!")
        else:
            print("Login failed!")
            return

    # Create a document
    print("\n3. Creating document...")
    doc = client.create_document("My Example Process")
    doc_id = doc["process_id"]
    print(f"   Created: {doc['title']} (ID: {doc_id})")

    # Add some blocks
    print("\n4. Adding blocks...")
    current_rev = doc["current_rev_number"]

    # Add heading
    result = client.insert_block(
        doc_id,
        current_rev,
        "Welcome to Block Editor",
        block_type="heading1"
    )
    if result and result.get("success"):
        current_rev = result["new_rev_number"]
        print(f"   ✓ Added heading (rev {current_rev})")
    else:
        print(f"   ✗ Failed to add heading: {result}")

    # Add paragraph
    result = client.insert_block(
        doc_id,
        current_rev,
        "This is a demonstration of the block-based editor.",
        block_type="paragraph"
    )
    if result and result.get("success"):
        current_rev = result["new_rev_number"]
        print(f"   ✓ Added paragraph (rev {current_rev})")
    else:
        print(f"   ✗ Failed to add paragraph: {result}")

    # Add todo list
    result = client.insert_block(
        doc_id,
        current_rev,
        "Create backend API",
        block_type="todo"
    )
    if result and result.get("success"):
        current_rev = result["new_rev_number"]
        print(f"   ✓ Added todo (rev {current_rev})")
    else:
        print(f"   ✗ Failed to add todo: {result}")

    result = client.insert_block(
        doc_id,
        current_rev,
        "Build Python client",
        block_type="todo"
    )
    if result and result.get("success"):
        current_rev = result["new_rev_number"]
        print(f"   ✓ Added todo (rev {current_rev})")
    else:
        print(f"   ✗ Failed to add todo: {result}")

    # List all blocks
    print("\n5. Listing blocks...")
    blocks = client.get_root_blocks(doc_id)
    if blocks:
        print(f"   Found {len(blocks)} blocks:")
        for block in blocks:
            print(f"   - [{block['block_type']}] {block['text'][:50]}")
    else:
        print("   Found 0 blocks or failed to retrieve blocks")
        blocks = []

    # Update a block
    if blocks:
        print("\n6. Updating first block...")
        first_block = blocks[0]
        result = client.update_block_text(
            doc_id,
            current_rev,
            str(first_block["block_id"]),
            "Welcome to Block Editor (Updated!)"
        )
        if result and result.get("success"):
            current_rev = result["new_rev_number"]
            print(f"   ✓ Updated block (rev {current_rev})")
        else:
            print(f"   ✗ Failed to update block: {result}")

    # List revisions
    print("\n7. Listing revisions...")
    revisions = client.list_revisions(doc_id)
    print(f"   Found {revisions['total']} revisions:")
    for rev in revisions["revisions"][:3]:  # Show first 3
        print(f"   - Rev {rev['rev_number']}: {rev['created_at']}")

    # Search
    print("\n8. Searching for 'welcome'...")
    search_results = client.search_document(doc_id, "welcome")
    print(f"   Found {search_results['total']} results:")
    for result in search_results["results"]:
        print(f"   - {result['snippet']}")

    # Export to Markdown
    print("\n9. Exporting to Markdown...")
    markdown = client.export_document(doc_id)
    print("   Exported content:")
    print("   ---")
    for line in markdown.split("\n")[:10]:  # Show first 10 lines
        print(f"   {line}")
    print("   ---")

    # Create share link
    print("\n10. Creating share link...")
    share_link = client.create_share_link(doc_id, expires_days=7)
    if share_link:
        print(f"   ✓ Share link: {client.base_url}/share/{share_link['token']}")
        print(f"   Expires in 7 days")

    # List all documents
    print("\n11. Listing all documents...")
    docs = client.list_documents()
    print(f"   Found {docs['total']} documents:")
    for d in docs["documents"]:
        print(f"   - {d['title']} (rev {d['current_rev_number']})")

    print("\n=== Demo Complete ===")
    print(f"\nYour document ID: {doc_id}")
    print(f"View API docs at: {client.base_url}/docs")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure the server is running:")
        print("  python run.py")

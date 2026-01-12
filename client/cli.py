#!/usr/bin/env python3
"""
Simple CLI client for Notion-style Block Editor
"""
import sys
import argparse
from getpass import getpass
from client.api_client import NotionClient

def main():
    client = NotionClient()

    parser = argparse.ArgumentParser(description="Notion-style Block Editor CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth commands
    auth_parser = subparsers.add_parser("register", help="Register a new user")
    auth_parser.add_argument("username")
    auth_parser.add_argument("email")

    login_parser = subparsers.add_parser("login", help="Login")
    login_parser.add_argument("username")

    subparsers.add_parser("me", help="Show current user info")

    # Document commands
    create_parser = subparsers.add_parser("create", help="Create a new document")
    create_parser.add_argument("title")

    subparsers.add_parser("list", help="List documents")

    get_parser = subparsers.add_parser("get", help="Get document")
    get_parser.add_argument("document_id")

    update_parser = subparsers.add_parser("update", help="Update document title")
    update_parser.add_argument("document_id")
    update_parser.add_argument("title")

    delete_parser = subparsers.add_parser("delete", help="Delete document")
    delete_parser.add_argument("document_id")

    restore_parser = subparsers.add_parser("restore", help="Restore document")
    restore_parser.add_argument("document_id")

    # Block commands
    blocks_parser = subparsers.add_parser("blocks", help="Get root blocks")
    blocks_parser.add_argument("document_id")

    add_parser = subparsers.add_parser("add", help="Add a block")
    add_parser.add_argument("document_id")
    add_parser.add_argument("text")
    add_parser.add_argument("--type", default="paragraph", choices=["paragraph", "heading1", "heading2", "list", "todo", "code", "quote"])

    edit_parser = subparsers.add_parser("edit", help="Edit block text")
    edit_parser.add_argument("document_id")
    edit_parser.add_argument("block_id")
    edit_parser.add_argument("text")

    del_block_parser = subparsers.add_parser("delete-block", help="Delete a block")
    del_block_parser.add_argument("document_id")
    del_block_parser.add_argument("block_id")

    # Revision commands
    revisions_parser = subparsers.add_parser("revisions", help="List revisions")
    revisions_parser.add_argument("document_id")

    restore_rev_parser = subparsers.add_parser("restore-rev", help="Restore to revision")
    restore_rev_parser.add_argument("document_id")
    restore_rev_parser.add_argument("rev_number", type=int)

    diff_parser = subparsers.add_parser("diff", help="Get diff between revisions")
    diff_parser.add_argument("document_id")
    diff_parser.add_argument("from_rev", type=int)
    diff_parser.add_argument("to_rev", type=int)

    # Search commands
    search_parser = subparsers.add_parser("search", help="Search all documents")
    search_parser.add_argument("query")

    search_doc_parser = subparsers.add_parser("search-doc", help="Search in document")
    search_doc_parser.add_argument("document_id")
    search_doc_parser.add_argument("query")

    # Import/Export commands
    export_parser = subparsers.add_parser("export", help="Export to Markdown")
    export_parser.add_argument("document_id")
    export_parser.add_argument("--output", "-o", help="Output file")

    import_parser = subparsers.add_parser("import", help="Import from Markdown")
    import_parser.add_argument("title")
    import_parser.add_argument("file")

    # Sharing commands
    invite_parser = subparsers.add_parser("invite", help="Invite user")
    invite_parser.add_argument("document_id")
    invite_parser.add_argument("email")
    invite_parser.add_argument("--role", default="viewer", choices=["viewer", "editor"])

    share_parser = subparsers.add_parser("share", help="Create share link")
    share_parser.add_argument("document_id")
    share_parser.add_argument("--expires", type=int, help="Expires in N days")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Handle commands
    try:
        if args.command == "register":
            password = getpass("Password: ")
            if client.register(args.username, args.email, password):
                print(f"✓ Registered user: {args.username}")
            else:
                print("✗ Registration failed")

        elif args.command == "login":
            password = getpass("Password: ")
            if client.login(args.username, password):
                print(f"✓ Logged in as: {args.username}")
            else:
                print("✗ Login failed")

        elif args.command == "me":
            user = client.get_me()
            if user:
                print(f"User ID: {user['user_id']}")
                print(f"Username: {user['username']}")
                print(f"Email: {user['email']}")

        elif args.command == "create":
            doc = client.create_document(args.title)
            if doc:
                print(f"✓ Created document: {doc['document_id']}")
                print(f"  Title: {doc['title']}")

        elif args.command == "list":
            result = client.list_documents()
            if result:
                print(f"Documents ({result['total']}):")
                for doc in result['documents']:
                    print(f"  [{doc['document_id']}] {doc['title']}")

        elif args.command == "get":
            doc = client.get_document(args.document_id)
            if doc:
                print(f"Document ID: {doc['document_id']}")
                print(f"Title: {doc['title']}")
                print(f"Owner: {doc['owner_id']}")
                print(f"Revision: {doc['current_rev_number']}")

        elif args.command == "update":
            doc = client.update_document(args.document_id, args.title)
            if doc:
                print(f"✓ Updated: {doc['title']}")

        elif args.command == "delete":
            if client.delete_document(args.document_id):
                print("✓ Document deleted")

        elif args.command == "restore":
            doc = client.restore_document(args.document_id)
            if doc:
                print(f"✓ Restored: {doc['title']}")

        elif args.command == "blocks":
            blocks = client.get_root_blocks(args.document_id)
            if blocks:
                print(f"Blocks ({len(blocks)}):")
                for block in blocks:
                    print(f"  [{block['block_id']}] {block['block_type']}: {block['text'][:50]}")

        elif args.command == "add":
            doc = client.get_document(args.document_id)
            if doc:
                result = client.insert_block(
                    args.document_id,
                    doc['current_rev_number'],
                    args.text,
                    args.type
                )
                if result and result.get('success'):
                    print(f"✓ Block added (rev {result['new_rev_number']})")
                elif result and result.get('conflicts'):
                    print("✗ Conflicts detected:")
                    for conflict in result['conflicts']:
                        print(f"  Block {conflict['block_id']}: {conflict['field']}")

        elif args.command == "edit":
            doc = client.get_document(args.document_id)
            if doc:
                result = client.update_block_text(
                    args.document_id,
                    doc['current_rev_number'],
                    args.block_id,
                    args.text
                )
                if result and result.get('success'):
                    print(f"✓ Block updated (rev {result['new_rev_number']})")

        elif args.command == "delete-block":
            doc = client.get_document(args.document_id)
            if doc:
                result = client.delete_block(
                    args.document_id,
                    doc['current_rev_number'],
                    args.block_id
                )
                if result and result.get('success'):
                    print(f"✓ Block deleted (rev {result['new_rev_number']})")

        elif args.command == "revisions":
            result = client.list_revisions(args.document_id)
            if result:
                print(f"Revisions ({result['total']}):")
                for rev in result['revisions']:
                    print(f"  Rev {rev['rev_number']}: {rev['created_at']}")

        elif args.command == "restore-rev":
            result = client.restore_revision(args.document_id, args.rev_number)
            if result:
                print(f"✓ Restored to revision {result['rev_number']}")

        elif args.command == "diff":
            result = client.get_diff(args.document_id, args.from_rev, args.to_rev)
            if result:
                print(f"Diff (rev {result['from_rev']} → {result['to_rev']}):")
                for change in result['changes']:
                    print(f"  {change['op_type']}: {change['block_id']}")

        elif args.command == "search":
            result = client.search(args.query)
            if result:
                print(f"Search results ({result['total']}):")
                for item in result['results']:
                    print(f"  [{item['block_id']}] {item['snippet']}")

        elif args.command == "search-doc":
            result = client.search_document(args.document_id, args.query)
            if result:
                print(f"Search results ({result['total']}):")
                for item in result['results']:
                    print(f"  [{item['block_id']}] {item['snippet']}")

        elif args.command == "export":
            markdown = client.export_document(args.document_id)
            if markdown:
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(markdown)
                    print(f"✓ Exported to {args.output}")
                else:
                    print(markdown)

        elif args.command == "import":
            with open(args.file, "r") as f:
                markdown = f.read()
            doc = client.import_document(args.title, markdown)
            if doc:
                print(f"✓ Imported as: {doc['document_id']}")

        elif args.command == "invite":
            if client.invite_user(args.document_id, args.email, args.role):
                print(f"✓ Invited {args.email} as {args.role}")

        elif args.command == "share":
            link = client.create_share_link(args.document_id, args.expires)
            if link:
                print(f"✓ Share link created:")
                print(f"  {client.base_url}/share/{link['token']}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

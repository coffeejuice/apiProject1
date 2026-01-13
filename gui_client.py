#!/usr/bin/env python3
"""
Tkinter-based GUI client for Notion-style Block Editor API
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import time
from typing import Optional, Dict, Any
from client.api_client import NotionClient


class APIClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Block Editor API Client")
        self.root.geometry("1400x800")

        # API Client
        self.client = NotionClient("http://localhost:8001")
        self.selected_document_id: Optional[str] = None
        self.selected_block: Optional[Dict[str, Any]] = None
        self.documents_data = []
        self.blocks_data = []

        # API Commands structure
        self.api_commands = {
            "Auth": {
                "Register": {"username": "str", "email": "str", "password": "str"},
                "Login": {"username": "str", "password": "str"},
                "Get Me": {}
            },
            "Documents": {
                "Create Document": {"title": "str"},
                "List Documents": {"page": "int", "page_size": "int"},
                "Get Document": {"document_id": "str"},
                "Update Document": {"document_id": "str", "title": "str"},
                "Delete Document": {"document_id": "str"},
                "Restore Document": {"document_id": "str"}
            },
            "Blocks": {
                "Get Root Blocks": {"document_id": "str"},
                "Get Block Children": {"block_id": "str"},
                "Insert Block": {"document_id": "str", "base_rev": "int", "text": "str", "block_type": "str", "parent_id": "str"},
                "Insert Block Before": {"document_id": "str", "base_rev": "int", "text": "str", "block_type": "str", "before_block_id": "str"},
                "Append Block After": {"document_id": "str", "base_rev": "int", "text": "str", "block_type": "str", "after_block_id": "str"},
                "Update Block Text": {"document_id": "str", "base_rev": "int", "block_id": "str", "text": "str"},
                "Delete Block": {"document_id": "str", "base_rev": "int", "block_id": "str"}
            },
            "Revisions": {
                "List Revisions": {"document_id": "str"},
                "Restore Revision": {"document_id": "str", "rev_number": "int"},
                "Get Diff": {"document_id": "str", "from_rev": "int", "to_rev": "int"}
            },
            "Sharing": {
                "Invite User": {"document_id": "str", "email": "str", "role": "str"},
                "Get ACL": {"document_id": "str"},
                "Revoke Access": {"document_id": "str", "user_id": "str"},
                "Create Share Link": {"document_id": "str", "expires_days": "int"}
            },
            "Search": {
                "Search All": {"query": "str", "limit": "int"},
                "Search Document": {"document_id": "str", "query": "str", "limit": "int"}
            },
            "Export/Import": {
                "Export Document": {"document_id": "str"},
                "Import Document": {"title": "str", "markdown": "str"}
            }
        }

        self.setup_ui()

    def setup_ui(self):
        # Main container with two columns
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left side (documents)
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=1)

        # Right side (API commands)
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=2)

        self.setup_left_side(left_frame)
        self.setup_right_side(right_frame)

    def setup_left_side(self, parent):
        # Split into three sections: users (top), documents (middle), blocks (bottom)
        left_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        left_paned.pack(fill=tk.BOTH, expand=True)

        # Top: Users and login
        users_frame = ttk.LabelFrame(left_paned, text="Login", padding=5)
        left_paned.add(users_frame, weight=0)

        # Username field
        user_row = ttk.Frame(users_frame)
        user_row.pack(fill=tk.X, pady=2)
        ttk.Label(user_row, text="User:", width=10).pack(side=tk.LEFT)

        self.username_entry = ttk.Entry(user_row)
        self.username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.username_entry.insert(0, "demo_user")

        # Password field
        pass_row = ttk.Frame(users_frame)
        pass_row.pack(fill=tk.X, pady=2)
        ttk.Label(pass_row, text="Password:", width=10).pack(side=tk.LEFT)

        self.password_entry = ttk.Entry(pass_row, show="*")
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.password_entry.insert(0, "password123")
        self.password_entry.bind('<Return>', lambda e: self.quick_login())

        # Login button
        self.login_button = ttk.Button(users_frame, text="Login", command=self.quick_login)
        self.login_button.pack(fill=tk.X, pady=(5, 0))

        # Status label
        self.login_status_label = ttk.Label(users_frame, text="Not logged in", foreground="red")
        self.login_status_label.pack(pady=(5, 0))

        # Middle: Documents list
        docs_frame = ttk.LabelFrame(left_paned, text="Documents", padding=5)
        left_paned.add(docs_frame, weight=1)

        # Toolbar
        toolbar = ttk.Frame(docs_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(toolbar, text="Refresh", command=lambda: self.refresh_documents(show_error=True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="New", command=self.create_document_dialog).pack(side=tk.LEFT, padx=2)

        # Documents listbox
        list_frame = ttk.Frame(docs_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.documents_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=False)
        self.documents_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.documents_listbox.bind('<<ListboxSelect>>', self.on_document_select)

        scrollbar.config(command=self.documents_listbox.yview)

        # Bottom: Document blocks view
        blocks_frame = ttk.LabelFrame(left_paned, text="Document Blocks", padding=5)
        left_paned.add(blocks_frame, weight=1)

        # Blocks listbox
        blocks_list_frame = ttk.Frame(blocks_frame)
        blocks_list_frame.pack(fill=tk.BOTH, expand=True)

        blocks_scrollbar = ttk.Scrollbar(blocks_list_frame)
        blocks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.blocks_listbox = tk.Listbox(blocks_list_frame, yscrollcommand=blocks_scrollbar.set, exportselection=False)
        self.blocks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.blocks_listbox.bind('<<ListboxSelect>>', self.on_block_select)

        blocks_scrollbar.config(command=self.blocks_listbox.yview)

    def setup_right_side(self, parent):
        # Split into upper and lower
        right_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)

        # Upper: API Commands TreeView
        upper_frame = ttk.LabelFrame(right_paned, text="API Commands", padding=5)
        right_paned.add(upper_frame, weight=1)

        self.commands_tree = ttk.Treeview(upper_frame, selectmode='browse')
        self.commands_tree.pack(fill=tk.BOTH, expand=True)
        self.commands_tree.bind('<<TreeviewSelect>>', self.on_command_select)

        self.populate_commands_tree()

        # Lower: Request/Response
        lower_frame = ttk.LabelFrame(right_paned, text="Request & Response", padding=5)
        right_paned.add(lower_frame, weight=2)

        # Input fields container (will be dynamic)
        self.input_frame = ttk.Frame(lower_frame)
        self.input_frame.pack(fill=tk.X, pady=(0, 5))

        self.input_widgets = {}

        # Send button
        ttk.Button(lower_frame, text="Send Request", command=self.send_request).pack(pady=5)

        # Response section
        response_label_frame = ttk.Frame(lower_frame)
        response_label_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(response_label_frame, text="Response:").pack(side=tk.LEFT)
        self.response_time_label = ttk.Label(response_label_frame, text="Time: - ms", foreground="blue")
        self.response_time_label.pack(side=tk.RIGHT)
        self.response_code_label = ttk.Label(response_label_frame, text="Code: -", foreground="green")
        self.response_code_label.pack(side=tk.RIGHT, padx=10)

        self.response_text = scrolledtext.ScrolledText(lower_frame, wrap=tk.WORD, height=15)
        self.response_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def populate_commands_tree(self):
        for category, commands in self.api_commands.items():
            category_node = self.commands_tree.insert('', 'end', text=category, tags=('category',))
            for command_name, params in commands.items():
                self.commands_tree.insert(category_node, 'end', text=command_name,
                                         values=(json.dumps(params),), tags=('command',))

        # Expand all
        for item in self.commands_tree.get_children():
            self.commands_tree.item(item, open=True)

    def on_command_select(self, event):
        selected = self.commands_tree.selection()
        if not selected:
            return

        item = selected[0]
        tags = self.commands_tree.item(item, 'tags')

        if 'command' in tags:
            command_name = self.commands_tree.item(item, 'text')
            params_json = self.commands_tree.item(item, 'values')[0]
            params = json.loads(params_json)

            self.create_input_fields(command_name, params)

    def create_input_fields(self, command_name: str, params: Dict[str, str]):
        # Clear previous inputs
        for widget in self.input_frame.winfo_children():
            widget.destroy()

        self.input_widgets.clear()

        ttk.Label(self.input_frame, text=f"Command: {command_name}",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        for param_name, param_type in params.items():
            row = ttk.Frame(self.input_frame)
            row.pack(fill=tk.X, pady=2)

            ttk.Label(row, text=f"{param_name} ({param_type}):", width=20).pack(side=tk.LEFT)

            entry = ttk.Entry(row, width=50)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Auto-fill document_id if available
            if param_name == "document_id" and self.selected_document_id:
                entry.insert(0, self.selected_document_id)

            # Auto-fill block_id if available
            elif param_name == "block_id" and self.selected_block:
                entry.insert(0, str(self.selected_block['block_id']))

            # Auto-fill before_block_id if available
            elif param_name == "before_block_id" and self.selected_block:
                entry.insert(0, str(self.selected_block['block_id']))

            # Auto-fill after_block_id if available
            elif param_name == "after_block_id" and self.selected_block:
                entry.insert(0, str(self.selected_block['block_id']))

            self.input_widgets[param_name] = entry

        self.current_command = command_name

    def send_request(self):
        if not hasattr(self, 'current_command'):
            messagebox.showwarning("No Command", "Please select a command first")
            return

        # Collect input values
        params = {}
        for param_name, widget in self.input_widgets.items():
            value = widget.get().strip()
            if value:
                # Try to convert to appropriate type
                if value.isdigit():
                    params[param_name] = int(value)
                else:
                    params[param_name] = value

        # Execute command
        start_time = time.time()
        result = self.execute_command(self.current_command, params)
        elapsed_time = (time.time() - start_time) * 1000  # milliseconds

        # Display response
        self.display_response(result, elapsed_time)

        # Refresh documents list if needed
        if self.current_command in ["Create Document", "Delete Document", "Restore Document", "Login"]:
            self.refresh_documents()

        # Refresh blocks view if current document affected
        if self.current_command in ["Insert Block", "Insert Block Before", "Append Block After", "Update Block Text", "Delete Block"] and self.selected_document_id:
            self.load_document_blocks(self.selected_document_id)

    def execute_command(self, command: str, params: Dict[str, Any]) -> Any:
        try:
            # Auth commands
            if command == "Register":
                return self.client.register(params['username'], params['email'], params['password'])
            elif command == "Login":
                return self.client.login(params['username'], params['password'])
            elif command == "Get Me":
                return self.client.get_me()

            # Document commands
            elif command == "Create Document":
                return self.client.create_document(params['title'])
            elif command == "List Documents":
                return self.client.list_documents(params.get('page', 1), params.get('page_size', 50))
            elif command == "Get Document":
                return self.client.get_document(params['document_id'])
            elif command == "Update Document":
                return self.client.update_document(params['document_id'], params['title'])
            elif command == "Delete Document":
                return self.client.delete_document(params['document_id'])
            elif command == "Restore Document":
                return self.client.restore_document(params['document_id'])

            # Block commands
            elif command == "Get Root Blocks":
                return self.client.get_root_blocks(params['document_id'])
            elif command == "Get Block Children":
                return self.client.get_block_children(params['block_id'])
            elif command == "Insert Block":
                return self.client.insert_block(
                    params['document_id'],
                    params['base_rev'],
                    params['text'],
                    params.get('block_type', 'paragraph'),
                    params.get('parent_id')
                )
            elif command == "Insert Block Before":
                return self.insert_block_before(
                    params['document_id'],
                    params['base_rev'],
                    params['text'],
                    params['before_block_id'],
                    params.get('block_type', 'paragraph')
                )
            elif command == "Append Block After":
                return self.append_block_after(
                    params['document_id'],
                    params['base_rev'],
                    params['text'],
                    params['after_block_id'],
                    params.get('block_type', 'paragraph')
                )
            elif command == "Update Block Text":
                return self.client.update_block_text(
                    params['document_id'],
                    params['base_rev'],
                    params['block_id'],
                    params['text']
                )
            elif command == "Delete Block":
                return self.client.delete_block(
                    params['document_id'],
                    params['base_rev'],
                    params['block_id']
                )

            # Revision commands
            elif command == "List Revisions":
                return self.client.list_revisions(params['document_id'])
            elif command == "Restore Revision":
                return self.client.restore_revision(params['document_id'], params['rev_number'])
            elif command == "Get Diff":
                return self.client.get_diff(params['document_id'], params['from_rev'], params['to_rev'])

            # Sharing commands
            elif command == "Invite User":
                return self.client.invite_user(params['document_id'], params['email'], params.get('role', 'viewer'))
            elif command == "Get ACL":
                return self.client.get_acl(params['document_id'])
            elif command == "Revoke Access":
                return self.client.revoke_access(params['document_id'], params['user_id'])
            elif command == "Create Share Link":
                return self.client.create_share_link(params['document_id'], params.get('expires_days'))

            # Search commands
            elif command == "Search All":
                return self.client.search(params['query'], params.get('limit', 50))
            elif command == "Search Document":
                return self.client.search_document(params['document_id'], params['query'], params.get('limit', 50))

            # Export/Import commands
            elif command == "Export Document":
                return self.client.export_document(params['document_id'])
            elif command == "Import Document":
                return self.client.import_document(params['title'], params['markdown'])

            else:
                return {"error": f"Unknown command: {command}"}

        except Exception as e:
            return {"error": str(e)}

    def display_response(self, result: Any, elapsed_time: float):
        self.response_text.delete(1.0, tk.END)

        # Update status labels
        self.response_time_label.config(text=f"Time: {elapsed_time:.2f} ms")

        if result is None:
            self.response_code_label.config(text="Code: Error", foreground="red")
            self.response_text.insert(1.0, "Request failed - check server logs")
        elif isinstance(result, dict) and 'error' in result:
            self.response_code_label.config(text="Code: Error", foreground="red")
            self.response_text.insert(1.0, json.dumps(result, indent=2))
        else:
            self.response_code_label.config(text="Code: 200", foreground="green")
            if isinstance(result, (dict, list)):
                self.response_text.insert(1.0, json.dumps(result, indent=2))
            elif isinstance(result, bool):
                self.response_text.insert(1.0, f"Success: {result}")
            else:
                self.response_text.insert(1.0, str(result))

    def refresh_documents(self, show_error=False):
        if not self.client.token:
            if show_error:
                messagebox.showwarning("Not Logged In", "Please login first using Auth → Login")
            return

        # Always silent in GUI mode - we handle errors in the GUI
        docs_result = self.client.list_documents(silent=True)
        self.documents_listbox.delete(0, tk.END)

        if docs_result and 'documents' in docs_result:
            self.documents_data = docs_result['documents']

            if len(self.documents_data) == 0:
                self.documents_listbox.insert(tk.END, "(No documents found - create one with 'New' button)")
            else:
                for doc in self.documents_data:
                    display_text = f"{doc['title']} (rev {doc['current_rev_number']})"
                    self.documents_listbox.insert(tk.END, display_text)
        else:
            self.documents_listbox.insert(tk.END, "(Failed to load documents - check if logged in)")

    def on_document_select(self, event):
        selection = self.documents_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        doc = self.documents_data[index]
        self.selected_document_id = str(doc['document_id'])

        self.load_document_blocks(self.selected_document_id)

        # Update document_id in currently displayed input fields if any
        if hasattr(self, 'input_widgets') and 'document_id' in self.input_widgets:
            self.input_widgets['document_id'].delete(0, tk.END)
            self.input_widgets['document_id'].insert(0, self.selected_document_id)

    def load_document_blocks(self, document_id: str):
        """Load all blocks (root and children) in hierarchical order"""
        root_blocks = self.client.get_root_blocks(document_id)

        self.blocks_listbox.delete(0, tk.END)
        self.blocks_data = []

        if root_blocks:
            for block in root_blocks:
                self._add_block_to_list(block, indent_level=0)
        else:
            self.blocks_listbox.insert(tk.END, "No blocks in this document")

    def _add_block_to_list(self, block: Dict[str, Any], indent_level: int):
        """Recursively add block and its children to the list with indentation"""
        block_type = block.get('block_type', 'unknown')
        text = block.get('text', '')

        # Create indented display text
        indent = "  " * indent_level  # 2 spaces per level
        display_text = f"{indent}[{block_type}] {text[:60]}{'...' if len(text) > 60 else ''}"

        self.blocks_listbox.insert(tk.END, display_text)
        self.blocks_data.append(block)

        # Recursively load children
        children = self.client.get_block_children(str(block['block_id']))
        if children:
            for child in children:
                self._add_block_to_list(child, indent_level + 1)

    def on_block_select(self, event):
        selection = self.blocks_listbox.curselection()
        if not selection:
            self.selected_block = None
            return

        index = selection[0]
        if index < len(self.blocks_data):
            self.selected_block = self.blocks_data[index]

            # Update block_id and related fields in currently displayed input fields if any
            # Note: parent_id is NOT auto-filled - leave empty for root level blocks
            if hasattr(self, 'input_widgets'):
                block_id_str = str(self.selected_block['block_id'])

                if 'block_id' in self.input_widgets:
                    self.input_widgets['block_id'].delete(0, tk.END)
                    self.input_widgets['block_id'].insert(0, block_id_str)

                if 'before_block_id' in self.input_widgets:
                    self.input_widgets['before_block_id'].delete(0, tk.END)
                    self.input_widgets['before_block_id'].insert(0, block_id_str)

                if 'after_block_id' in self.input_widgets:
                    self.input_widgets['after_block_id'].delete(0, tk.END)
                    self.input_widgets['after_block_id'].insert(0, block_id_str)

    def quick_login(self):
        """Quick login using credentials from login pane"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showwarning("Invalid Input", "Please enter username and password")
            return

        # Attempt login
        success = self.client.login(username, password)

        if success:
            self.login_status_label.config(text=f"Logged in as {username}", foreground="green")
            self.login_button.config(text="Logout", command=self.logout)
            # Auto-refresh documents
            self.refresh_documents()
        else:
            self.login_status_label.config(text="Login failed", foreground="red")
            messagebox.showerror("Login Failed", "Invalid username or password")

    def logout(self):
        """Logout current user"""
        self.client.token = None
        self.client._save_config()
        self.login_status_label.config(text="Not logged in", foreground="red")
        self.login_button.config(text="Login", command=self.quick_login)
        # Clear documents and blocks
        self.documents_listbox.delete(0, tk.END)
        self.blocks_listbox.delete(0, tk.END)
        self.documents_data = []
        self.blocks_data = []

    def insert_block_before(self, document_id: str, base_rev: int, text: str,
                           before_block_id: str, block_type: str = "paragraph") -> Optional[Dict]:
        """Insert a new block before the specified block"""
        from uuid import uuid4
        import time

        # Find the target block in our loaded blocks data
        target_block = None
        for block in self.blocks_data:
            if str(block['block_id']) == before_block_id:
                target_block = block
                break

        if not target_block:
            return {"error": "Target block not found"}

        # Get parent_id and order_key from target block
        parent_id = target_block.get('parent_block_id')
        target_order_key = target_block.get('order_key', '')

        # Generate an order_key that comes before the target block
        # Decrement the timestamp portion slightly
        if target_order_key:
            try:
                # Parse existing order key (format: timestamp-random)
                parts = target_order_key.split('-')
                if len(parts) == 2:
                    timestamp = int(parts[0])
                    # Create a key slightly before the target
                    new_order_key = f"{timestamp - 1000:020d}-9999"
                else:
                    # Fallback to simple string comparison
                    new_order_key = f"{int(time.time() * 1000000) - 1000000:020d}-0000"
            except:
                new_order_key = f"{int(time.time() * 1000000) - 1000000:020d}-0000"
        else:
            new_order_key = f"{int(time.time() * 1000000):020d}-0000"

        # Create the insert operation
        ops = [{
            "op_type": "insert_block",
            "data": {
                "block_id": str(uuid4()),
                "parent_block_id": parent_id,
                "order_key": new_order_key,
                "block_type": block_type,
                "text": text,
                "props": {}
            }
        }]

        return self.client.commit(document_id, base_rev, ops)

    def append_block_after(self, document_id: str, base_rev: int, text: str,
                           after_block_id: str, block_type: str = "paragraph") -> Optional[Dict]:
        """Append a new block after the specified block"""
        from uuid import uuid4
        import time

        # Find the target block in our loaded blocks data
        target_block = None
        for block in self.blocks_data:
            if str(block['block_id']) == after_block_id:
                target_block = block
                break

        if not target_block:
            return {"error": "Target block not found"}

        # Get parent_id and order_key from target block
        parent_id = target_block.get('parent_block_id')
        target_order_key = target_block.get('order_key', '')

        # Generate an order_key that comes after the target block
        # Increment the timestamp portion slightly
        if target_order_key:
            try:
                # Parse existing order key (format: timestamp-random)
                parts = target_order_key.split('-')
                if len(parts) == 2:
                    timestamp = int(parts[0])
                    # Create a key slightly after the target
                    new_order_key = f"{timestamp + 1000:020d}-0000"
                else:
                    # Fallback to simple string comparison
                    new_order_key = f"{int(time.time() * 1000000) + 1000000:020d}-0000"
            except:
                new_order_key = f"{int(time.time() * 1000000) + 1000000:020d}-0000"
        else:
            new_order_key = f"{int(time.time() * 1000000):020d}-0000"

        # Create the insert operation
        ops = [{
            "op_type": "insert_block",
            "data": {
                "block_id": str(uuid4()),
                "parent_block_id": parent_id,
                "order_key": new_order_key,
                "block_type": block_type,
                "text": text,
                "props": {}
            }
        }]

        return self.client.commit(document_id, base_rev, ops)

    def create_document_dialog(self):
        if not self.client.token:
            messagebox.showinfo("Not Logged In", "Please login first")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Create Document")
        dialog.geometry("400x100")

        ttk.Label(dialog, text="Document Title:").pack(pady=10)
        title_entry = ttk.Entry(dialog, width=40)
        title_entry.pack(pady=5)
        title_entry.focus()

        def create():
            title = title_entry.get().strip()
            if title:
                result = self.client.create_document(title)
                if result:
                    messagebox.showinfo("Success", f"Document created: {result.get('title')}")
                    self.refresh_documents()
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to create document")

        ttk.Button(dialog, text="Create", command=create).pack(pady=10)


def main():
    root = tk.Tk()
    app = APIClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

import requests
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import json
from pathlib import Path

class NotionClient:
    """Simple Python client for Notion-style Block Editor API"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.device_id: UUID = uuid4()
        self.offline_queue: List[Dict] = []
        self.config_file = Path.home() / ".notion_client_config.json"
        self._load_config()

    def _load_config(self):
        """Load saved config (token, device_id)"""
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                config = json.load(f)
                self.token = config.get("token")
                self.device_id = UUID(config.get("device_id", str(uuid4())))

    def _save_config(self):
        """Save config to file"""
        with open(self.config_file, "w") as f:
            json.dump({
                "token": self.token,
                "device_id": str(self.device_id)
            }, f)

    def _headers(self) -> Dict[str, str]:
        """Get request headers with auth"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, endpoint: str, silent: bool = False, **kwargs) -> Optional[Dict]:
        """Make HTTP request"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, headers=self._headers(), **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            if not silent:
                print(f"Request failed: {e}")
            return None

    # Auth methods
    def register(self, username: str, email: str, password: str) -> bool:
        """Register a new user"""
        data = {"login": username, "email": email, "password": password}
        result = self._request("POST", "/auth/register", json=data)
        return result is not None

    def login(self, username: str, password: str) -> bool:
        """Login and store token"""
        data = {"login": username, "password": password}
        result = self._request("POST", "/auth/login", json=data)
        if result and "access_token" in result:
            self.token = result["access_token"]
            self._save_config()
            print("✓ Logged in successfully")
            return True
        return False

    def get_me(self) -> Optional[Dict]:
        """Get current user info"""
        return self._request("GET", "/auth/me")

    # Process methods
    def create_document(self, title: str) -> Optional[Dict]:
        """Create a new document"""
        data = {"title": title}
        return self._request("POST", "/documents", json=data)

    def list_documents(self, page: int = 1, page_size: int = 50, silent: bool = False) -> Optional[Dict]:
        """List all accessible documents"""
        return self._request("GET", f"/documents?page={page}&page_size={page_size}", silent=silent)

    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document by ID"""
        return self._request("GET", f"/documents/{document_id}")

    def update_document(self, document_id: str, title: str) -> Optional[Dict]:
        """Update document title"""
        data = {"title": title}
        return self._request("PATCH", f"/documents/{document_id}", json=data)

    def delete_document(self, document_id: str) -> bool:
        """Soft delete a document"""
        result = self._request("DELETE", f"/documents/{document_id}")
        return result is not None

    def restore_document(self, document_id: str) -> Optional[Dict]:
        """Restore a deleted document"""
        return self._request("POST", f"/documents/{document_id}/restore")

    # Block methods
    def get_root_blocks(self, document_id: str) -> Optional[List[Dict]]:
        """Get root-level blocks"""
        return self._request("GET", f"/documents/{document_id}/blocks/root")

    def get_block_children(self, block_id: str) -> Optional[List[Dict]]:
        """Get children of a block"""
        return self._request("GET", f"/blocks/{block_id}/children")

    def commit(self, document_id: str, base_rev: int, ops: List[Dict]) -> Optional[Dict]:
        """Commit operations to document"""
        data = {
            "device_id": str(self.device_id),
            "base_rev_number": base_rev,
            "client_batch_id": str(uuid4()),
            "ops": ops
        }
        return self._request("POST", f"/documents/{document_id}/commit", json=data)

    # Revision methods
    def list_revisions(self, document_id: str) -> Optional[Dict]:
        """List document revisions"""
        return self._request("GET", f"/documents/{document_id}/revisions")

    def restore_revision(self, document_id: str, rev_number: int) -> Optional[Dict]:
        """Restore document to specific revision"""
        return self._request("POST", f"/documents/{document_id}/revisions/{rev_number}/restore")

    def get_diff(self, document_id: str, from_rev: int, to_rev: int) -> Optional[Dict]:
        """Get diff between two revisions"""
        return self._request("GET", f"/documents/{document_id}/revisions/diff?from={from_rev}&to={to_rev}")

    # Sharing methods
    def invite_user(self, document_id: str, email: str, role: str = "viewer") -> bool:
        """Invite user to document"""
        data = {"email": email, "role": role}
        result = self._request("POST", f"/documents/{document_id}/invites", json=data)
        return result is not None

    def get_acl(self, document_id: str) -> Optional[List[Dict]]:
        """Get document ACL"""
        return self._request("GET", f"/documents/{document_id}/acl")

    def revoke_access(self, document_id: str, user_id: str) -> bool:
        """Revoke user access"""
        result = self._request("DELETE", f"/documents/{document_id}/acl/{user_id}")
        return result is not None

    def create_share_link(self, document_id: str, expires_days: Optional[int] = None) -> Optional[Dict]:
        """Create public share link"""
        params = f"?expires_days={expires_days}" if expires_days else ""
        return self._request("POST", f"/documents/{document_id}/share-links{params}")

    # Search methods
    def search(self, query: str, limit: int = 50) -> Optional[Dict]:
        """Search across all documents"""
        return self._request("GET", f"/search?q={query}&limit={limit}")

    def search_document(self, document_id: str, query: str, limit: int = 50) -> Optional[Dict]:
        """Search within a document"""
        return self._request("GET", f"/documents/{document_id}/search?q={query}&limit={limit}")

    # Import/Export methods
    def export_document(self, document_id: str) -> Optional[str]:
        """Export document to Markdown"""
        result = self._request("GET", f"/documents/{document_id}/export")
        return result.get("markdown") if result else None

    def import_document(self, title: str, markdown: str) -> Optional[Dict]:
        """Import Markdown as new document"""
        data = {"title": title, "markdown": markdown}
        return self._request("POST", "/documents/import", json=data)

    # Helper methods for common operations
    def insert_block(self, document_id: str, base_rev: int, text: str,
                    block_type: str = "paragraph", parent_id: Optional[str] = None) -> Optional[Dict]:
        """Insert a new block"""
        import time
        import random
        order_key = f"{int(time.time() * 1000000):020d}-{random.randint(1000, 9999)}"

        ops = [{
            "op_type": "insert_block",
            "data": {
                "block_id": str(uuid4()),
                "parent_block_id": parent_id,
                "order_key": order_key,
                "block_type": block_type,
                "text": text,
                "props": {}
            }
        }]
        return self.commit(document_id, base_rev, ops)

    def update_block_text(self, document_id: str, base_rev: int, block_id: str, text: str) -> Optional[Dict]:
        """Update block text"""
        ops = [{
            "op_type": "update_text",
            "data": {
                "block_id": block_id,
                "text": text
            }
        }]
        return self.commit(document_id, base_rev, ops)

    def delete_block(self, document_id: str, base_rev: int, block_id: str) -> Optional[Dict]:
        """Delete a block"""
        ops = [{
            "op_type": "delete_block",
            "data": {
                "block_id": block_id
            }
        }]
        return self.commit(document_id, base_rev, ops)

import requests
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.device_id: UUID = uuid4()

    def set_token(self, token: str):
        self.token = token

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, headers=self._headers(), **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except Exception as e:
            print(f"API Error ({method} {endpoint}): {e}")
            return None

    # Auth
    def login(self, username, password):
        data = {"login": username, "password": password}
        res = self.request("POST", "/auth/login", json=data)
        if res and "access_token" in res:
            self.set_token(res["access_token"])
            return True
        return False

    # Documents
    def list_documents(self):
        return self.request("GET", "/documents")

    def create_document(self, title: str):
        return self.request("POST", "/documents", json={"title": title})

    def get_document(self, doc_id):
        return self.request("GET", f"/documents/{doc_id}")

    def get_blocks(self, doc_id):
        return self.request("GET", f"/documents/{doc_id}/blocks/root")

    def commit(self, doc_id, base_rev, ops):
        data = {
            "device_id": str(self.device_id),
            "base_rev_number": base_rev,
            "client_batch_id": str(uuid4()),
            "ops": ops
        }
        return self.request("POST", f"/documents/{doc_id}/commit", json=data)

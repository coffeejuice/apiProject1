import requests
import json

BASE_URL = "http://localhost:8001"

def test_key_like_search():
    # 1. Login as admin
    login_data = {"login": "demo_user", "password": "password123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = resp.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    print("Testing key_like search...")

    # 2. Search for 'svc.worker.%'
    # First, let's ensure some data exists
    requests.post(f"{BASE_URL}/settings/provision/apply", headers=headers)

    # Now search
    query = "key_like=worker.%"
    resp = requests.get(f"{BASE_URL}/settings/?{query}", headers=headers)
    settings = resp.json()
    
    print(f"Found {len(settings)} settings matching 'worker.%':")
    for s in settings:
        print(f" - {s['key']} = {s['value']}")
        assert "worker." in s['key']

    print("✓ key_like search verified successfully!")

if __name__ == "__main__":
    try:
        test_key_like_search()
    except Exception as e:
        print(f"Test failed: {e}")

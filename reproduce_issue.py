import requests
import json

BASE_URL = "http://127.0.0.1:8001"

def test_create_document():
    # 1. Login to get token
    login_url = f"{BASE_URL}/auth/login"
    login_data = {
        "login": "testuser",
        "password": "password123"
    }
    
    print(f"Logging in to {login_url}...")
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code != 200:
            print(f"Login failed: {response.status_code} {response.text}")
            # Try register if login failed (maybe user doesn't exist)
            register_url = f"{BASE_URL}/auth/register"
            register_data = {
                "login": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
            print(f"Attempting registration at {register_url}...")
            response = requests.post(register_url, json=register_data)
            if response.status_code != 200 and response.status_code != 201:
                 print(f"Registration failed: {response.status_code} {response.text}")
                 return
            
            # Login again after registration
            response = requests.post(login_url, json=login_data)
            if response.status_code != 200:
                print(f"Login failed after registration: {response.status_code} {response.text}")
                return

        token = response.json().get("access_token")
        print("Login successful.")
        
        # 2. Try to create document
        create_url = f"{BASE_URL}/documents"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        doc_data = {
            "title": "Reproduction Doc",
            "material_id": 1
        }
        
        print(f"Creating document at {create_url}...")
        response = requests.post(create_url, json=doc_data, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_create_document()

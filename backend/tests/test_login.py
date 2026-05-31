import requests

url = "http://localhost:8001/auth/login"
data = {"login": "demo_user", "password": "password123"}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")

import requests

url = "http://localhost:8001/auth/register"
data = {
    "login": "new_user_1",
    "email": "new_user@example.com",
    "password": "password123",
    "full_name": "New User"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")

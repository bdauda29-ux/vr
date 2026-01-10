from app.main import app
from app import auth
from flask import json

def test_list_staff():
    # Create a valid token
    token = auth.create_access_token(data={"sub": "admin", "role": "super_admin", "id": 1})
    
    with app.test_client() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/staff", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print("Response Body:", response.get_data(as_text=True))
        else:
            data = json.loads(response.get_data(as_text=True))
            print(f"Success! Retrieved {len(data)} staff records.")
            if len(data) > 0:
                print("First record sample:", data[0])

if __name__ == "__main__":
    test_list_staff()

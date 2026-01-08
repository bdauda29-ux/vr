import urllib.request
import json

def test_url(url):
    print(f"Testing {url}...")
    try:
        with urllib.request.urlopen(url) as response:
            print(f"Status: {response.getcode()}")
            data = response.read()
            try:
                json_data = json.loads(data)
                print(f"JSON Data count: {len(json_data)}")
                if len(json_data) > 0:
                    print("First item:", json_data[0])
            except:
                print("Response is not JSON")
    except Exception as e:
        print(f"Error: {e}")

test_url("http://127.0.0.1:8000/staff")
test_url("http://127.0.0.1:8000/audit-logs")

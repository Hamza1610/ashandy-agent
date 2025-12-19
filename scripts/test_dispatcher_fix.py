"""
Test script to verify dispatcher routing fix.
"""
import requests
import json

# Test endpoint
url = "http://127.0.0.1:8000/api/test/message"

# Test payload - same as the failing case
payload = {
    "message": "My name is Israel",
    "user_id": "Israel",
    "platform": "test"
}

print("Testing dispatcher fix...")
print(f"Sending: {payload['message']}")
print("-" * 50)

try:
    response = requests.post(url, json=payload, timeout=30)
    result = response.json()
    
    print(f"Status: {result.get('status')}")
    print(f"AI Response: {result.get('ai_response')}")
    
    if result.get('error'):
        print(f"\nERROR: {result.get('error')}")
    else:
        if result.get('ai_response') and 'Israel' in result.get('ai_response', ''):
            print("\nSUCCESS: Worker executed and responded correctly!")
        else:
            print(f"\nWARNING: Got response but content unexpected: {result.get('ai_response')}")
            
except requests.exceptions.ConnectionError:
    print("ERROR: Server not running. Start with: python app/main.py")
except Exception as e:
    print(f"ERROR: Test failed: {e}")

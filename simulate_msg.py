import requests
import json
import time

URL = "http://localhost:8000/webhook/whatsapp"

def send_message(text, user_id="2348000000001"):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": user_id,
                        "id": f"wamid.{int(time.time())}",
                        "timestamp": str(int(time.time())),
                        "text": {"body": text},
                        "type": "text"
                    }]
                }
            }]
        }]
    }
    
    print(f"\n📤 Sending User Message: '{text}'")
    try:
        response = requests.post(URL, json=payload)
        print(f"📥 Server Response: {response.status_code}")
        try:
            print(f"   Body: {response.json()}")
        except:
            print(f"   Body: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("--- 🧪 Delivery System Test Simulation ---")
    print("Ensure 'uvicorn app.main:app --reload' is running in another terminal.\n")
    
    # Step 1: Initialize Chat / Buy
    input("Press Enter to send Step 1 (Buying items)...")
    send_message("I want to buy the Matte Powder and 2 Lip Glosses.")
    
    # Step 2: Request Delivery
    input("\nPress Enter to send Step 2 (Requesting Delivery to Bodija)...")
    send_message("I am in Ibadan. I want Delivery to 15, Bodija Estate, Ibadan.")
    
    print("\n✅ Simulation Complete. Check your Server Logs for 'Delivery Fee' calculations!")

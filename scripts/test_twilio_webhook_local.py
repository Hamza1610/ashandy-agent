"""
Test Twilio Webhook: Simulates an incoming message from Twilio.
"""
import httpx
import asyncio

async def test_twilio_webhook():
    url = "http://localhost:8000/webhook/twilio/whatsapp"
    
    # Mock Twilio Form Data
    data = {
        "From": "whatsapp:+2349026880099",
        "Body": "Hello world from Twilio test",
        "NumMedia": "0",
        "AccountSid": "ACxxxxxxxx",
        "MessageSid": "SMxxxxxxxx"
    }
    
    print(f"Sending POST to {url}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == 200:
                print("✅ Test Passed: Webhook processed successfully (Status 200).")
            else:
                print("❌ Test Failed: valid response not received.")
                
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("Ensure the server is running on localhost:8000")

if __name__ == "__main__":
    asyncio.run(test_twilio_webhook())

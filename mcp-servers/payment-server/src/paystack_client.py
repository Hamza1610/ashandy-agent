import httpx
import os
import logging
import uuid
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment-client")

class PaystackClient:
    def __init__(self):
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
        if not self.secret_key:
            logger.error("PAYSTACK_SECRET_KEY is missing! Client initialization incomplete.")
        
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    async def initialize_transaction(self, email: str, amount_ngn: float, user_id: str) -> str:
        """
        Initialize a Paystack transaction.
        Args:
            email: Customer email.
            amount_ngn: Amount in Naira (e.g. 5000).
            user_id: User ID for metadata.
        Returns:
            JSON string with authorization_url and reference.
        """
        url = f"{self.base_url}/transaction/initialize"
        
        # Convert to Kobo
        amount_kobo = int(float(amount_ngn) * 100)
        reference = f"ASHDY_{uuid.uuid4().hex[:12]}"
        
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": {"user_id": user_id, "source": "ashandy_agent_mcp"}
        }

        logger.info(f"Initializing Payment for {email}: {amount_ngn} NGN")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                
                if response.status_code != 200:
                    return f"Error: Paystack API failed ({response.status_code}) - {response.text}"
                
                data = response.json()
                if data.get("status"):
                    # Return formatted string for Agent usage
                    auth_url = data["data"]["authorization_url"]
                    ref = data["data"]["reference"]
                    return f"SUCCESS|{auth_url}|{ref}"
                else:
                    return f"Error: {data.get('message')}"

        except Exception as e:
            logger.error(f"Paystack Init Error: {e}")
            return f"Error: Connection Failed - {str(e)}"

    async def verify_transaction(self, reference: str) -> str:
        """
        Verify status of a transaction.
        """
        url = f"{self.base_url}/transaction/verify/{reference}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                 
                if response.status_code != 200:
                    return f"Error: Verification failed ({response.status_code})"
                
                data = response.json()
                if data.get("status"):
                    tx_data = data["data"]
                    status = tx_data.get("status")
                    amount = float(tx_data.get("amount", 0)) / 100
                    return f"Transaction Status: {status.upper()} | Amount: ₦{amount:,.2f}"
                else:
                    return f"Error: {data.get('message')}"
                    
        except Exception as e:
             logger.error(f"Paystack Verify Error: {e}")
             return f"Error: Verify Connection Failed - {str(e)}"

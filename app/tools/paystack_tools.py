from langchain.tools import tool
from app.services.paystack_service import paystack_service

@tool
async def generate_payment_link(email: str, amount: float, reference: str) -> str:
    """Generate a payment link for a customer using Paystack."""
    # Amount comes in as Naira (e.g. 5000), update to kobo for Paystack
    amount_kobo = int(amount * 100)
    response = paystack_service.initialize_transaction(email, amount_kobo, reference)
    
    if response and response.get('status'):
        return f"Payment Link: {response['data']['authorization_url']}"
    return "Failed to generate payment link."

@tool
async def verify_payment(reference: str) -> str:
    """Verify a payment transaction given a reference."""
    response = paystack_service.verify_transaction(reference)
    if response and response.get('status'):
        return f"Payment Verified: {response['data']['status']}"
    return "Payment verification failed."

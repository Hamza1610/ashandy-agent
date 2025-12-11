"""
Payment tools for Paystack integration.
Renamed from paystack_tools.py for consistency.
"""
from langchain.tools import tool
from app.services.paystack_service import paystack_service
import logging

logger = logging.getLogger(__name__)


@tool("generate_payment_link_tool")
async def generate_payment_link(email: str, amount: float, reference: str) -> str:
    """
    Generate a Paystack payment link for a customer order.
    
    Args:
        email: Customer's email address
        amount: Order amount in Naira (e.g., 5000.00)
        reference: Unique order reference ID
        
    Returns:
        Payment link URL or error message
    """
    try:
        logger.info(f"Generating payment link: amount={amount}, ref={reference}")
        
        # Convert to kobo (Paystack requirement)
        amount_kobo = int(amount * 100)
        
        response = paystack_service.initialize_transaction(
            email=email,
            amount=amount_kobo,
            reference=reference
        )
        
        if response and response.get('status'):
            payment_url = response['data']['authorization_url']
            return f"Payment link generated successfully: {payment_url}\n\nAmount: ₦{amount:,.2f}\nPlease click the link to complete your payment."
        
        logger.error(f"Paystack initialization failed: {response}")
        return "Failed to generate payment link. Please try again or contact support."
        
    except Exception as e:
        logger.error(f"Payment link generation error: {e}")
        return f"Error creating payment link: {str(e)}"


@tool("verify_payment_tool")
async def verify_payment(reference: str) -> str:
    """
    Verify a payment transaction status.
    
    Args:
        reference: The payment reference ID to verify
        
    Returns:
        Payment verification status
    """
    try:
        logger.info(f"Verifying payment: {reference}")
        
        response = paystack_service.verify_transaction(reference)
        
        if response and response.get('status'):
            status = response['data']['status']
            amount = response['data']['amount'] / 100  # Convert from kobo
            
            return f"Payment Status: {status}\nAmount: ₦{amount:,.2f}\nReference: {reference}"
        
        return f"Could not verify payment for reference: {reference}"
        
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        return f"Payment verification failed: {str(e)}"

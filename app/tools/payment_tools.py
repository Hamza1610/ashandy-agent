"""
Payment Tools: Paystack integration for payment link generation and verification.
"""
from langchain_core.tools import tool
from app.services.mcp_service import mcp_service
import logging

logger = logging.getLogger(__name__)

DEFAULT_EMAIL = "ashandyawelewa@gmail.com"


@tool("generate_payment_link_tool")
async def generate_payment_link(amount: float, reference: str, email: str = None, delivery_details: dict = None) -> str:
    """
    Generate a Paystack payment link. Requires delivery_details for delivery orders.
    
    Args:
        amount: Total amount in Naira
        reference: Unique reference/user ID
        email: Customer email (defaults to ashandyawelewa@gmail.com)
        delivery_details: Dict with name, phone, address
    """
    # Validate delivery details
    if delivery_details:
        missing = []
        if not delivery_details.get('name'):
            missing.append('full name')
        if not delivery_details.get('phone'):
            missing.append('phone number')
        if not delivery_details.get('address'):
            missing.append('delivery address')
        
        if missing:
            return f"❌ Cannot generate payment. Missing: {', '.join(missing)}.\n\nPlease provide: Full Name, Phone, Address."
    
    final_email = email if (email and '@' in email) else DEFAULT_EMAIL
    logger.info(f"Generating payment link: amount={amount}, ref={reference}")
    
    result = await mcp_service.call_tool("payment", "initialize_payment", {
        "email": final_email,
        "amount_ngn": amount,
        "user_id": reference
    })
    
    if result.startswith("SUCCESS"):
        parts = result.split("|")
        payment_url = parts[1]
        actual_ref = parts[2] if len(parts) > 2 else reference
        
        delivery_msg = ""
        if delivery_details:
            delivery_msg = f"\n\n📦 *Delivery To:*\n{delivery_details.get('name', 'N/A')}\n{delivery_details.get('address', 'N/A')}\n📞 {delivery_details.get('phone', 'N/A')}"
        
        return f"""✅ Payment link ready!

💰 *Amount:* ₦{amount:,.2f}
🧾 *Reference:* {actual_ref}
📧 *Receipt to:* {final_email}{delivery_msg}

🔗 *Click to pay:* {payment_url}

Once paid, we'll confirm and process your delivery!"""
    
    return f"Failed to generate payment link: {result}"


@tool("verify_payment_tool")
async def verify_payment(reference: str) -> str:
    """Verify a payment transaction status."""
    logger.info(f"Verifying payment: {reference}")
    return await mcp_service.call_tool("payment", "verify_payment", {"reference": reference})

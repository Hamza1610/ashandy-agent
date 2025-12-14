"""
Payment tools for Paystack integration.
Includes delivery validation before payment link generation.
"""
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

# Fallback email for Paystack (same as in delivery_validation_tools)
DEFAULT_EMAIL = "ashandyawelewa@gmail.com"


@tool("generate_payment_link_tool")
async def generate_payment_link(
    amount: float, 
    reference: str,
    email: str = None,
    delivery_details: dict = None
) -> str:
    """
    Generate a Paystack payment link via MCP Payment Server.
    
    IMPORTANT: This tool requires delivery_details to be validated BEFORE calling.
    If delivery details are missing, the tool will return an error asking for them.
    
    Args:
        amount: Total amount in Naira
        reference: Unique reference/user ID
        email: Customer email (optional, defaults to ashandyawelewa@gmail.com)
        delivery_details: Dict with name, phone, address (required for delivery orders)
    
    Returns:
        Payment link or error message
    """
    from app.services.mcp_service import mcp_service
    
    # Validate delivery details if provided
    if delivery_details:
        missing = []
        if not delivery_details.get('name'):
            missing.append('full name')
        if not delivery_details.get('phone'):
            missing.append('phone number')
        if not delivery_details.get('address'):
            missing.append('delivery address')
        
        if missing:
            logger.warning(f"Missing delivery details: {missing}")
            return f"❌ Cannot generate payment link. Missing: {', '.join(missing)}.\n\nPlease ask the customer to provide their:\n• Full Name\n• Phone Number\n• Delivery Address"
    
    # Use fallback email if not provided
    final_email = email if (email and '@' in email) else DEFAULT_EMAIL
    
    logger.info(f"Generating payment link via MCP: amount={amount}, ref={reference}, email={final_email}")
    
    result = await mcp_service.call_tool("payment", "initialize_payment", {
        "email": final_email,
        "amount_ngn": amount,
        "user_id": reference
    })
    
    # MCP returns "SUCCESS|URL|REF" or "Error:..."
    if result.startswith("SUCCESS"):
        parts = result.split("|")
        payment_url = parts[1]
        actual_ref = parts[2] if len(parts) > 2 else reference
        
        # Include delivery confirmation in response
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
    """
    Verify a payment transaction status via MCP Payment Server.
    """
    logger.info(f"Verifying payment via MCP: {reference}")
    from app.services.mcp_service import mcp_service

    result = await mcp_service.call_tool("payment", "verify_payment", {"reference": reference})
    return result


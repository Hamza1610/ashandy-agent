"""
Fallback Payment Tools: Manual payment and error recovery options.
"""
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

# Store bank account details (should be in config/env in production)
BANK_DETAILS = {
    "bank_name": "GTBank",
    "account_number": "0123456789",
    "account_name": "Ashandy Cosmetics Ltd",
    "whatsapp_support": "+234 XXX XXX XXXX"
}


@tool
async def get_manual_payment_instructions(amount: float, user_id: str, order_summary: str = "") -> str:
    """Provide manual bank transfer instructions when payment link fails.
    
    Args:
        amount: Total amount to pay
        user_id: User identifier for reference
        order_summary: Optional order details to include
        
    Returns:
        Formatted manual payment instructions
    """
    try:
        logger.info(f"💳 Providing manual payment instructions for {user_id}, amount: ₦{amount:,.0f}")
        
        instructions = f"""⚠️ **Payment Link Temporarily Unavailable**

No worries! You can complete payment via bank transfer:

🏦 **Bank Transfer Details:**
Bank: {BANK_DETAILS['bank_name']}
Account Number: {BANK_DETAILS['account_number']}
Account Name: {BANK_DETAILS['account_name']}

💰 **Amount to Transfer:** ₦{amount:,.2f}
🧾 **Payment Reference:** {user_id}

📝 **Important:**
1. Transfer ₦{amount:,.2f} to the account above
2. Use reference: {user_id}
3. Send proof of payment (screenshot) to {BANK_DETAILS['whatsapp_support']}
4. We'll confirm within 1 hour and process your order!"""

        if order_summary:
            instructions += f"\n\n📦 **Your Order:**\n{order_summary}"
        
        instructions += "\n\n✨ We'll send confirmation once payment is verified!"
        
        return instructions
        
    except Exception as e:
        logger.error(f"Error generating manual payment instructions: {e}")
        return f"❌ Error: {str(e)}. Please contact support at {BANK_DETAILS['whatsapp_support']}"


@tool
async def check_api_health() -> str:
    """Check if payment APIs are available.
    
    Returns:
        Status message about API availability
    """
    try:
        from app.services.mcp_service import mcp_service
        
        # Quick health check
        result = await mcp_service.call_tool("payment", "verify_payment", {"reference": "health_check"})
        
        if "error" in result.lower() or "failed" in result.lower():
            return "⚠️ Payment system temporarily unavailable. Manual payment option available."
        
        return "✅ Payment system operational."
        
    except Exception as e:
        logger.error(f"API health check failed: {e}")
        return "⚠️ Payment system status unknown. Manual payment recommended."

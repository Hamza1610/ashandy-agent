"""
Payment tools for Paystack integration.
Renamed from paystack_tools.py for consistency.
"""
from langchain.tools import tool

import logging

logger = logging.getLogger(__name__)


@tool("generate_payment_link_tool")
async def generate_payment_link(email: str, amount: float, reference: str) -> str:
    """
    Generate a Paystack payment link via MCP Payment Server.
    """
    logger.info(f"Generating payment link via MCP: amount={amount}, ref={reference}")
    from app.services.mcp_service import mcp_service

    # Using 'ashandy-payment' server logic via standard tool call
    # Note: Logic for Payment init needs User ID, but tool strict args don't usually provide it naturally.
    # The MCP tool expects (email, amount_ngn, user_id).
    # We will pass 'unknown_user' if not available, OR rely on this tool being called with sufficient context.
    # For now, we fit the signature.
    
    result = await mcp_service.call_tool("payment", "initialize_payment", {
        "email": email,
        "amount_ngn": amount,
        "user_id": reference  # Using ref as user_id proxy if needed, or update signature
    })
    
    # MCP returns "SUCCESS|URL|REF" or "Error:..."
    if result.startswith("SUCCESS"):
        parts = result.split("|")
        payment_url = parts[1]
        return f"Payment link generated successfully: {payment_url}\n\nAmount: ₦{amount:,.2f}\nPlease click the link to complete your payment."
    
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

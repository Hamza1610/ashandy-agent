"""
Simple payment request tool for sales agent.
The sales agent calls this to indicate customer wants to pay.
The payment agent then handles the actual Paystack link generation.
"""
from langchain.tools import tool
import logging

logger = logging.getLogger(__name__)

@tool("request_payment_link")
async def request_payment_link(product_names: str, total_amount: float) -> str:
    """
    Request payment link generation for customer purchase.
    Call this tool when customer confirms they want to buy products.
    
    Args:
        product_names: Names of products customer wants to buy (e.g., "10 PAIRS LASH SET, RINGLIGHT")
        total_amount: Total cost in Naira (e.g., 13500.00)
    
    Returns:
        Confirmation message that payment link will be sent
    """
    print(f"\n>>> TOOL: request_payment_link called")
    print(f">>> Products: {product_names}")
    print(f">>> Amount: ₦{total_amount:,.2f}")
    
    logger.info(f"Payment requested: {product_names} = ₦{total_amount:,.2f}")
    
    # This tool just signals intent - the payment agent will generate the actual link
    return f"✅ Payment link requested for {product_names} (₦{total_amount:,.2f}). Generating your payment link now..."

"""
Email collection tool: Asks customer for email before payment.
"""
from langchain.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
async def request_customer_email() -> str:
    """
    Request customer's email address for payment processing.
    
    Call this tool BEFORE requesting payment link when email is not available.
    The customer will be prompted to provide their email.
    
    Returns:
        Message asking customer for email
        
    Example:
        >>> await request_customer_email.ainvoke({})
        "Please provide your email address for payment"
    """
    print(f"\n>>> TOOL: request_customer_email called")
    logger.info("Requesting customer email for payment")
    
    return "Please provide your email address to complete your order and receive payment confirmation."

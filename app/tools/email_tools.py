"""
Email Tools: Request customer email for payment processing.
"""
from langchain.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
async def request_customer_email() -> str:
    """Request customer email before payment link generation."""
    logger.info("Requesting customer email")
    return "Please provide your email address to complete your order and receive payment confirmation."

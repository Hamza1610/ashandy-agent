from mcp.server.fastmcp import FastMCP
from src.paystack_client import PaystackClient
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Server
mcp = FastMCP("ashandy-payment")
client = PaystackClient()

@mcp.tool()
async def initialize_payment(email: str, amount_ngn: float, user_id: str) -> str:
    """
    Generate a Paystack Payment Link.
    Args:
        email: Customer email
        amount_ngn: Amount in Naira (e.g. 5000)
        user_id: User ID
    Returns:
        String containing 'SUCCESS|URL|REF' or Error message.
    """
    return await client.initialize_transaction(email, amount_ngn, user_id)

@mcp.tool()
async def verify_payment(reference: str) -> str:
    """
    Verify a transaction status by Reference.
    """
    return await client.verify_transaction(reference)

if __name__ == "__main__":
    mcp.run()

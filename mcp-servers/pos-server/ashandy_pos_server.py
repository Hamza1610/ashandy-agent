from mcp.server.fastmcp import FastMCP
from src.pos_client import PHPPOSClient
import logging

# Initialize Server
mcp = FastMCP("ashandy-pos")

# Initialize Client
client = PHPPOSClient()

@mcp.tool()
async def search_products(query: str) -> str:
    """
    Search for products in the PHPPOS inventory.
    Args:
        query: Name or ID of the product.
    Returns:
        Formatted string with stock, price, and ID.
    """
    return await client.search_items(query)

@mcp.tool()
async def check_stock(item_id: str) -> str:
    """
    Check specific stock for an Item ID.
    Args:
        item_id: The PHPPOS Item ID.
    """
    # Re-use search logic for now as it handles IDs too, 
    # but we could add specific endpoint logic in client later.
    return await client.search_items(item_id)

if __name__ == "__main__":
    mcp.run()

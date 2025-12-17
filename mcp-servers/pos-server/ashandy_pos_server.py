from mcp.server.fastmcp import FastMCP
from src.pos_client import PHPPOSClient
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

@mcp.tool()
async def get_product_details(item_id: str) -> str:
    """
    Get detailed information about a product/item from PHPPOS.
    Args:
        item_id: Unfortunately named 'item_id' in generic POS terms, equal to product_id.
    """
    return await client.get_item_details(item_id)

@mcp.tool()
async def create_order(order_json: str) -> str:
    """
    Create a new order/sale in PHPPOS.
    Args:
        order_json: VALID JSON string containing sale data.
                   Structure: {"items": [{"item_id": "123", "quantity": 1}], "customer_id": "..."}
    """
    import json
    try:
        data = json.loads(order_json)
        return await client.create_sale(data)
    except json.JSONDecodeError:
        return "Error: Invalid JSON format for order data."

@mcp.tool()
async def get_order(order_id: str) -> str:
    """
    Get details of a specific order/sale from PHPPOS.
    Args:
        order_id: The Sale ID.
    """
    return await client.get_sale(order_id)

if __name__ == "__main__":
    mcp.run()

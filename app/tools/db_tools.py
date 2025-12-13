from langchain.tools import tool
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.models.db_models import User, Product, Order
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

@tool
async def check_admin_whitelist(phone_number: str) -> bool:
    """Check if a phone number is in the admin whitelist (via environment variable)."""
    from app.utils.config import settings
    if phone_number in settings.ADMIN_PHONE_NUMBERS:
        return True
    return False

@tool
async def get_product_details(product_name_or_sku: str) -> str:
    """Retrieve product details from the POS system by name or SKU."""
    from app.services.mcp_service import mcp_service
    # Reuse search logic as it is fuzzy
    return await mcp_service.call_tool("pos", "search_products", {"query": product_name_or_sku})

@tool
async def create_order_record(user_id: str, amount: float, reference: str, details: Dict = None) -> str:
    """Create a new order/sale in the POS system."""
    from app.services.mcp_service import mcp_service
    import json
    
    # Construct sale data for POS
    # We map 'details' to 'items' if possible, or send a generic structure
    # details is expected to function as the items list in the new architecture
    
    sale_data = {
        "customer_id": user_id, # Assuming mapping or passing raw ID
        "items": details.get("items", []) if details else [],
        "reference": reference,
        "amount": amount
    }
    
    response = await mcp_service.call_tool("pos", "create_order", {"order_json": json.dumps(sale_data)})
    return response

@tool
async def get_order_by_reference(reference: str) -> Dict:
    """Retrieve an order by its reference ID (Sale ID) from POS."""
    from app.services.mcp_service import mcp_service
    import json
    
    result = await mcp_service.call_tool("pos", "get_order", {"order_id": reference})
    
    if "not found" in result.lower() or "error" in result.lower():
        return {}
        
    try:
        # If result is JSON string, parse it
        # The MCP tool returns a string representation of the dict or usage verification
        # Ideally we parse it back to dict for the agent
        # However, the tool returns 'str', need to be careful if it's not valid JSON
        # The pos_client returns str(sale) which uses Python's single quotes.
        # This is a bit messy for 'Dict' return type.
        # But let's return the string or a simple dict wrapping the strings.
        return {"raw_data": result}
    except:
        return {}

@tool
async def get_active_order_reference(user_id: str) -> str:
    """
    Retrieve the reference of a recent order. 
    (Refactored to ask user or check recent interactions in Memory/POS - Placeholder)
    """
    return "Please provide the Order ID or Reference Number."

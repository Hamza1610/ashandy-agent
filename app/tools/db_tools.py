"""
Database Tools: Order management and admin verification.
"""
from langchain.tools import tool
from app.services.mcp_service import mcp_service
from app.utils.config import settings
import logging
import json

logger = logging.getLogger(__name__)


@tool
async def check_admin_whitelist(phone_number: str) -> bool:
    """Check if a phone number is in the admin whitelist."""
    return phone_number in settings.ADMIN_PHONE_NUMBERS


@tool
async def get_product_details(product_name_or_sku: str) -> str:
    """Retrieve product details from POS by name or SKU."""
    return await mcp_service.call_tool("pos", "search_products", {"query": product_name_or_sku})


@tool
async def create_order_record(user_id: str, amount: float, reference: str, details: dict = None) -> str:
    """Create a new order in the POS system."""
    sale_data = {
        "customer_id": user_id,
        "items": details.get("items", []) if details else [],
        "reference": reference,
        "amount": amount
    }
    return await mcp_service.call_tool("pos", "create_order", {"order_json": json.dumps(sale_data)})


@tool
async def get_order_by_reference(reference: str) -> dict:
    """Retrieve an order by reference ID from POS."""
    result = await mcp_service.call_tool("pos", "get_order", {"order_id": reference})
    if "not found" in result.lower() or "error" in result.lower():
        return {}
    return {"raw_data": result}


@tool
async def get_active_order_reference(user_id: str) -> str:
    """Get user's recent order reference (placeholder)."""
    return "Please provide the Order ID or Reference Number."

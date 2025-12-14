"""
Logistics Tools: Geocoding and delivery fee calculation via MCP.
"""
from langchain.tools import tool
from app.services.mcp_service import mcp_service
import logging
import ast

logger = logging.getLogger(__name__)


@tool
async def geocode_address(address: str) -> dict:
    """Geocode an address. Returns: {lat, lng, formatted_address}"""
    logger.info(f"Geocoding: {address}")
    try:
        result_str = await mcp_service.call_tool("logistics", "geocode_address", {"address": address})
        try:
            return ast.literal_eval(result_str)
        except:
            return {"result": result_str}
    except Exception as e:
        logger.error(f"Geocode Error: {e}")
        return {"error": str(e)}


@tool
async def calculate_delivery_fee(destination_address: str) -> dict:
    """Calculate delivery fee for an address."""
    logger.info(f"Calculating fee: {destination_address}")
    try:
        result_str = await mcp_service.call_tool("logistics", "calculate_delivery_fees", {"destination": destination_address})
        return {"formatted_response": result_str}
    except Exception as e:
        logger.error(f"Fee Calculation Error: {e}")
        return {"error": str(e)}

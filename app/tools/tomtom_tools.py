from langchain.tools import tool
import logging

logger = logging.getLogger(__name__)

@tool
async def geocode_address(address: str) -> dict:
    """
    Geocodes an address using Logistics MCP Server.
    Returns: dict with lat, lng, formatted_address.
    """
    logger.info(f"Geocoding via MCP: {address}")
    try:
        from app.services.mcp_service import mcp_service
        
        # Call 'geocode_address' on 'logistics' server
        result_str = await mcp_service.call_tool("logistics", "geocode_address", {"address": address})
        
        # Attempt to parse string back to dict for Agent compatibility
        import ast
        try:
             # FastMCP returns string repr of dict, so safe eval works
             return ast.literal_eval(result_str)
        except:
             return {"result": result_str}
             
    except Exception as e:
        logger.error(f"MCP Geocode Error: {e}")
        return {"error": str(e)}

@tool
async def calculate_delivery_fee(destination_address: str) -> dict:
    """
    Calculates delivery fee via Logistics MCP Server.
    Returns: dict with fee details or error.
    """
    logger.info(f"Calculating fee via MCP for: {destination_address}")
    try:
        from app.services.mcp_service import mcp_service
        
        # Call 'calculate_delivery_fees' on 'logistics' server
        result_str = await mcp_service.call_tool("logistics", "calculate_delivery_fees", {"destination": destination_address})
        
        # Return as a wrapped dict since the agent might expect structured output
        # The string itself contains newlines and formatted text which is good for the final user response.
        return {"formatted_response": result_str}
        
    except Exception as e:
        logger.error(f"MCP Fee Calculation Error: {e}")
        return {"error": str(e)}

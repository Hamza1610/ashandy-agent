from typing import Dict, Any
from app.models.agent_states import AgentState
from app.tools.tomtom_tools import calculate_delivery_fee
from langchain_core.messages import SystemMessage
import logging
import json

logger = logging.getLogger(__name__)

async def delivery_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Delivery Agent:
    - Calculates delivery fees using TomTom API.
    - Updates state with fee and formatting.
    """
    logger.info("Delivery Agent processing...")
    
    delivery_details = state.get("delivery_details", {})
    if not delivery_details:
        # Should ideally prompt back, but assuming Sales Agent collects this first.
        # If missing, we might assume pickup or error.
        return {}

    address = f"{delivery_details.get('address', '')}, {delivery_details.get('city', '')}, {delivery_details.get('state', '')}"
    
    logger.info(f"Calculating delivery for: {address}")
    
    # Call TomTom Tool
    try:
        result = calculate_delivery_fee.invoke(address)
        
        if result.get("error"):
            logger.error(f"Delivery calculation error: {result['error']}")
            # Fallback logic or error reporting
            return {"delivery_fee": None, "error": f"Delivery Error: {result['error']}"}
            
        fee = result.get("fee", 0)
        distance = result.get("distance_text", "Unknown")
        
        logger.info(f"Delivery Fee: {fee} ({distance})")
        
        return {
            "delivery_fee": fee,
            "error": None
            # We don't necessarily need to add a message here, 
            # as the Sales Agent will compose the final invoice.
        }
        
    except Exception as e:
        logger.error(f"Delivery Agent failed: {e}")
        return {"error": str(e)}

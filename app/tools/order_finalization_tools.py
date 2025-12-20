"""
Order Finalization Tools: Calculate final totals with delivery fees.
"""
from langchain_core.tools import tool
from typing import List, Dict
import logging
import re

logger = logging.getLogger(__name__)


@tool
async def get_order_total_with_delivery(
    ordered_items: List[Dict],
    delivery_location: str,
    delivery_type: str = "delivery"
) -> dict:
    """Calculate complete order total including cart subtotal and delivery fee.
    
    Args:
        ordered_items: Cart items with name, price, quantity
        delivery_location: Delivery address/city for fee calculation
        delivery_type: 'delivery' or 'pickup'
        
    Returns:
        Dict with subtotal, delivery_fee, total, and formatted breakdown
    """
    try:
        logger.info(f"\ud83d\udce6 Calculating final total for {len(ordered_items)} items to {delivery_location}")
        
        if not ordered_items:
            return {"error": "Cart is empty"}
        
        # Calculate cart subtotal
        subtotal = sum(item.get('price', 0) * item.get('quantity', 0) for item in ordered_items)
        
        # Calculate delivery fee
        delivery_fee = 0.0
        delivery_status = ""
        
        if delivery_type.lower() == "pickup":
            delivery_fee = 0.0
            delivery_status = "FREE (Pickup)"
        else:
            try:
                from app.tools.tomtom_tools import calculate_delivery_fee
                delivery_result = await calculate_delivery_fee.ainvoke({"location": delivery_location})
                
                # Extract fee from result
                fee_match = re.search(r'₦([\\d,]+)', str(delivery_result))
                if fee_match:
                    delivery_fee = float(fee_match.group(1).replace(',', ''))
                    delivery_status = f"₦{delivery_fee:,.0f} (to {delivery_location})"
                else:
                    # Couldn't parse - use default or error
                    logger.warning(f"Could not parse delivery fee from: {delivery_result}")
                    delivery_fee = 1500.0  # Default fallback
                    delivery_status = f"₦{delivery_fee:,.0f} (estimated)"
            except Exception as e:
                logger.error(f"Delivery fee calculation failed: {e}")
                delivery_fee = 1500.0  # Fallback
                delivery_status = f"₦{delivery_fee:,.0f} (standard rate)"
        
        # Calculate grand total
        grand_total = subtotal + delivery_fee
        
        # Format breakdown
        items_list = "\\n".join([
            f"  • {item.get('name')} x{item.get('quantity')} @ ₦{item.get('price', 0):,.0f} = ₦{item.get('price', 0) * item.get('quantity', 0):,.0f}"
            for item in ordered_items
        ])
        
        formatted_breakdown = f"""📦 **ORDER SUMMARY**

**Items:**
{items_list}

**Subtotal:** ₦{subtotal:,.0f}
**Delivery:** {delivery_status}
{"─" * 40}
**GRAND TOTAL:** ₦{grand_total:,.0f}"""
        
        return {
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total": grand_total,
            "breakdown": formatted_breakdown,
            "delivery_location": delivery_location,
            "delivery_type": delivery_type
        }
        
    except Exception as e:
        logger.error(f"Error calculating order total with delivery: {e}", exc_info=True)
        return {"error": f"Failed to calculate total: {str(e)}"}


@tool
async def format_order_summary(order_total_data: dict) -> str:
    """Format order total data into customer-friendly summary.
    
    Args:
        order_total_data: Dict from get_order_total_with_delivery
        
    Returns:
        Formatted order summary string
    """
    try:
        if "error" in order_total_data:
            return f"❌ {order_total_data['error']}"
        
        return order_total_data.get("breakdown", "Error formatting summary")
        
    except Exception as e:
        logger.error(f"Error formatting order summary: {e}")
        return f"❌ Error: {str(e)}"

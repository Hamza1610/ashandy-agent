"""
Order Management Tools: Convert cart to structured order data for payment.
"""
from langchain_core.tools import tool
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


@tool
async def create_order_from_cart(
    ordered_items: List[Dict], 
    delivery_type: str = "delivery",
    delivery_details: Dict = None
) -> dict:
    """Create structured order data from cart items.
    
    Args:
        ordered_items: List of cart items with name, price, quantity
        delivery_type: 'delivery' or 'pickup'
        delivery_details: Optional delivery info (name, phone, address)
        
    Returns:
        Structured order_data dict with items, subtotal, delivery info
    """
    try:
        logger.info(f"📦 Creating order from {len(ordered_items)} cart items")
        
        if not ordered_items:
            return {"error": "Cart is empty. Cannot create order."}
        
        # Calculate subtotal
        subtotal = sum(item.get('price', 0) * item.get('quantity', 0) for item in ordered_items)
        
        # Build structured order
        order_data = {
            "items": ordered_items,
            "subtotal": subtotal,
            "delivery_type": delivery_type.lower(),
            "delivery_details": delivery_details or {},
            "status": "pending_payment"
        }
        
        logger.info(f"📦 Order created: {len(ordered_items)} items, ₦{subtotal:,.0f} subtotal")
        
        return order_data
        
    except Exception as e:
        logger.error(f"Error creating order from cart: {e}", exc_info=True)
        return {"error": f"Failed to create order: {str(e)}"}


@tool
async def get_cart_total(ordered_items: List[Dict], delivery_location: str = None) -> str:
    """Calculate total from cart items and optionally include delivery fee.
    
    Args:
        ordered_items: List of cart items
        delivery_location: Optional delivery location to calculate delivery fee
        
    Returns:
        Formatted string with cart summary, subtotal, delivery fee, and grand total
    """
    try:
        if not ordered_items:
            return "🛒 Cart is empty."
        
        subtotal = sum(item.get('price', 0) * item.get('quantity', 0) for item in ordered_items)
        
        items_str = "\n".join([
            f"• {item.get('name')} x{item.get('quantity')} @ ₦{item.get('price', 0):,.0f}"
            for item in ordered_items
        ])
        
        response = f"""🛒 **Cart Summary:**
{items_str}

**Subtotal:** ₦{subtotal:,.0f}"""
        
        # Calculate delivery fee if location provided
        if delivery_location:
            try:
                from app.tools.tomtom_tools import calculate_delivery_fee
                delivery_result = await calculate_delivery_fee.ainvoke({"location": delivery_location})
                
                # Extract fee from result (assuming format: "Delivery fee: ₦X" or similar)
                import re
                fee_match = re.search(r'₦([\d,]+)', str(delivery_result))
                if fee_match:
                    delivery_fee = float(fee_match.group(1).replace(',', ''))
                    grand_total = subtotal + delivery_fee
                    response += f"\n**Delivery Fee ({delivery_location}):** ₦{delivery_fee:,.0f}"
                    response += f"\n\n📦 **GRAND TOTAL:** ₦{grand_total:,.0f}"
                else:
                    response += f"\n(Delivery fee to be calculated for {delivery_location})"
            except Exception as e:
                logger.debug(f"Could not calculate delivery fee: {e}")
                response += "\n(Delivery fee will be added based on location)"
        else:
            response += "\n(Delivery fee will be added based on location)"
        
        return response
        
    except Exception as e:
        logger.error(f"Error calculating cart total: {e}")
        return f"❌ Error calculating total: {str(e)}"


@tool
async def validate_order_ready(ordered_items: List[Dict], delivery_type: str = "delivery") -> dict:
    """Check if order is ready for payment processing.
    
    Args:
        ordered_items: Cart items
        delivery_type: 'delivery' or 'pickup'
        
    Returns:
        Dict with ready status and any issues
    """
    try:
        issues = []
        
        if not ordered_items or len(ordered_items) == 0:
            issues.append("Cart is empty")
        
        # Validate items have required fields
        for idx, item in enumerate(ordered_items):
            if not item.get('name'):
                issues.append(f"Item {idx+1} missing product name")
            if not item.get('price') or item.get('price') <= 0:
                issues.append(f"Item {idx+1} has invalid price")
            if not item.get('quantity') or item.get('quantity') <= 0:
                issues.append(f"Item {idx+1} has invalid quantity")
        
        return {
            "ready": len(issues) == 0,
            "issues": issues,
            "item_count": len(ordered_items)
        }
        
    except Exception as e:
        logger.error(f"Error validating order: {e}")
        return {"ready": False, "issues": [f"Validation error: {str(e)}"]}

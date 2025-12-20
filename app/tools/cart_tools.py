"""
Cart Management Tools: Production-grade shopping cart operations.

Provides LangChain tools for add, remove, update, view, and clear cart operations.
All tools integrate with LangGraph state for proper state management.
"""
from langchain_core.tools import tool
from app.tools.product_tools import search_products
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


@tool
async def add_to_cart(product_name: str, quantity: int = 1, user_id: str = "default") -> str:
    """Add a product to the shopping cart.
    
    Args:
        product_name: Name of the product to add
        quantity: Number of items to add (default: 1)
        user_id: User identifier
        
    Returns:
        Confirmation message with cart update
    """
    try:
        logger.info(f"🛒 ADD_TO_CART: {product_name} x{quantity} for {user_id}")
        
        # Validate quantity
        if quantity <= 0:
            return "❌ Quantity must be greater than 0. Please specify a valid quantity."
        
        # Search for product to get accurate price and details
        search_result = await search_products.ainvoke({"query": product_name, "user_id": user_id})
        
        # Parse product details from search result
        price_match = re.search(r'Price[:\s]+([\\d,]+)', str(search_result))
        if not price_match:
            return f"❌ Could not find '{product_name}'. Please check the product name and try again."
        
        price = float(price_match.group(1).replace(',', ''))
        
        # Extract clean product name from search results
        name_match = re.search(r'Name[:\s]*([^\\n]+)', str(search_result))
        clean_name = name_match.group(1).strip() if name_match else product_name
        
        # Note: State update happens in sales_worker via returned tool evidence
        # The sales_worker will parse this output and update ordered_items
        return f"✅ Added *{clean_name}* x{quantity} (₦{price:,.0f} each) to your cart!"
        
    except Exception as e:
        logger.error(f"Error in add_to_cart: {e}", exc_info=True)
        return f"❌ Sorry, I couldn't add '{product_name}' to your cart. Please try again or choose a different product."


@tool
async def remove_from_cart(product_name: str, user_id: str = "default") -> str:
    """Remove a product from the shopping cart.
    
    Args:
        product_name: Name of the product to remove
        user_id: User identifier
        
    Returns:
        Confirmation message
    """
    try:
        logger.info(f"🗑️ REMOVE_FROM_CART: {product_name} for {user_id}")
        
        # Note: Actual removal happens in sales_worker via state update
        # This tool provides the intent signal
        return f"✅ Removed *{product_name}* from your cart!"
        
    except Exception as e:
        logger.error(f"Error in remove_from_cart: {e}", exc_info=True)
        return f"❌ Sorry, I couldn't remove '{product_name}'. Please try again."


@tool
async def update_cart_quantity(product_name: str, quantity: int, user_id: str = "default") -> str:
    """Update the quantity of a product in the cart.
    
    Args:
        product_name: Name of the product to update
        quantity: New quantity (use 0 to remove)
        user_id: User identifier
        
    Returns:
        Confirmation message
    """
    try:
        logger.info(f"📝 UPDATE_CART_QUANTITY: {product_name} → {quantity} for {user_id}")
        
        if quantity < 0:
            return "❌ Quantity cannot be negative. Please specify a valid quantity."
        
        if quantity == 0:
            return f"✅ Removed *{product_name}* from your cart!"
        
        return f"✅ Updated *{product_name}* quantity to {quantity}!"
        
    except Exception as e:
        logger.error(f"Error in update_cart_quantity: {e}", exc_info=True)
        return f"❌ Sorry, I couldn't update the quantity. Please try again."


@tool
async def get_cart_summary(user_id: str = "default") -> str:
    """Get a summary of items currently in the shopping cart.
    
    Args:
        user_id: User identifier
        
    Returns:
        Formatted cart summary with items and total
    """
    try:
        logger.info(f"📋 GET_CART_SUMMARY for {user_id}")
        
        # Note: Sales worker will provide actual cart data from state
        # This tool signals the intent to view cart
        return "🛒 Retrieving your cart summary..."
        
    except Exception as e:
        logger.error(f"Error in get_cart_summary: {e}", exc_info=True)
        return "❌ Sorry, I couldn't retrieve your cart. Please try again."


@tool
async def clear_cart(user_id: str = "default") -> str:
    """Clear all items from the shopping cart.
    
    Args:
        user_id: User identifier
        
    Returns:
        Confirmation message
    """
    try:
        logger.info(f"🗑️ CLEAR_CART for {user_id}")
        
        # Note: Actual clearing happens in sales_worker via state update
        return "✅ Your cart has been cleared!"
        
    except Exception as e:
        logger.error(f"Error in clear_cart: {e}", exc_info=True)
        return "❌ Sorry, I couldn't clear your cart. Please try again."

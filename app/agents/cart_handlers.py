"""
Cart handler functions for sales_worker.
Direct state management approach - no tool enforcement needed.
"""
from typing import Optional

async def handle_cart_operations(user_msg: str, task_desc: str, state: dict, user_id: str) -> Optional[str]:
    """
    Detect and handle cart operations directly without tool calls.
    
    Args:
        user_msg: Latest user message
        task_desc: Task description from planner
        state: Agent state
        user_id: User identifier
        
    Returns:
        Response message if cart operation detected, None otherwise
    """
    from app.tools.product_tools import search_products
    import re
    import logging
    
    logger = logging.getLogger(__name__)
    
    msg_lower = user_msg.lower()
    task_lower = task_desc.lower()
    combined = f"{msg_lower} {task_lower}"
    
    ordered_items = state.get("ordered_items", [])
    
    # ========== ADD TO CART ==========
    if any(phrase in combined for phrase in [
        "i'll take", "i want", "add to cart", "add to order",
        "i'll buy", "get me", "purchase", "buy"
    ]):
        product_name = extract_product_name(user_msg)
        if product_name and len(product_name) > 2:
            try:
                logger.info(f"🛒 ADD TO CART: Searching for '{product_name}'")
                
                # Search for product
                search_result = await search_products.ainvoke({
                    "query": product_name,
                    "user_id": user_id
                })
                
                # ✨ NEW: Extract and validate actual product from search results
                validated_product = extract_product_from_search(search_result, product_name)
                
                if validated_product:
                    # Product found! Add to cart
                    ordered_items.append({
                        "name": validated_product["name"],
                        "price": validated_product["price"],
                        "quantity": 1
                    })
                    state["ordered_items"] = ordered_items
                    
                    logger.info(f"✅ Added {validated_product['name']} @ ₦{validated_product['price']:,} to cart")
                    return f"✅ Added *{validated_product['name']}* (₦{validated_product['price']:,}) to your cart!\n\nWant to add anything else or ready to checkout?"
                else:
                    # Product not found in search results
                    logger.warning(f"❌ Product '{product_name}' not found in search results")
                    return f"❌ Sorry, I couldn't find '{product_name.title()}' in our store. Could you check the spelling or try a different product?"
                    
            except Exception as e:
                logger.error(f"❌ Add to cart failed: {e}")
                return f"❌ Sorry, I had trouble adding '{product_name}'. Please try again."
    
    # ========== VIEW CART ==========
    if any(phrase in combined for phrase in [
        "show cart", "view cart", "my cart", "what's in", "cart summary",
        "what did i order", "my order"
    ]):
        logger.info(f"🛒 VIEW CART: {len(ordered_items)} items")
        
        if not ordered_items:
            return "🛒 Your cart is empty! What would you like to add?"
        
        # Build cart summary
        total = sum(item['price'] * item['quantity'] for item in ordered_items)
        items_text = "\n".join([
            f"{i+1}. *{item['name']}* x{item['quantity']} - ₦{item['price'] * item['quantity']:,}"
            for i, item in enumerate(ordered_items)
        ])
        
        return f"🛒 **YOUR CART**\n\n{items_text }\n\n**Total:** ₦{total:,}\n\nReady to checkout?"
    
    # ========== REMOVE FROM CART ==========
    if "remove" in combined or "delete" in combined:
        product_name = extract_product_name(user_msg)
        
        for i, item in enumerate(ordered_items):
            if product_name.lower() in item['name'].lower():
                removed = ordered_items.pop(i)
                state["ordered_items"] = ordered_items
                logger.info(f"🗑️ Removed {removed['name']} from cart")
                return f"✅ Removed *{removed['name']}* from your cart!"
        
        return f"❌ Couldn't find '{product_name}' in your cart."
    
    # ========== UPDATE QUANTITY ==========
    if ("make" in combined or "change" in combined) and any(char.isdigit() for char in user_msg):
        qty = extract_quantity(user_msg)
        product_name = extract_product_name(user_msg)
        
        if qty and product_name:
            for item in ordered_items:
                if product_name.lower() in item['name'].lower():
                    old_qty = item['quantity']
                    item['quantity'] = qty
                    state["ordered_items"] = ordered_items
                    logger.info(f"🔢 Updated {item['name']}: {old_qty} → {qty}")
                    return f"✅ Updated *{item['name']}* from {old_qty} to {qty} units!"
            
            return f"❌ Couldn't find '{product_name}' in your cart."
    
    # ========== CLEAR CART ==========
    if ("clear" in combined or "empty" in combined) and "cart" in combined:
        count = len(ordered_items)
        state["ordered_items"] = []
        logger.info(f"🗑️ Cleared {count} items from cart")
        return f"✅ Cleared {count} item(s) from your cart!"
    
    # No cart operation detected
    return None


def extract_product_name(msg: str) -> str:
    """Extract product name from user message."""
    import re
    
    # Remove common phrases using word boundaries to avoid breaking brand names
    cleaned = msg.lower()
    
    # List of phrases to remove (order matters - longer phrases first)
    phrases = [
        r"\bi'?ll\s+take\b", r"\bi\s+want\b", r"\badd\s+to\s+cart\b", 
        r"\badd\s+to\s+order\b", r"\bi'?ll\s+buy\b", r"\bget\s+me\b",
        r"\bpurchase\b", r"\bbuy\b", r"\badd\b", r"\bremove\b", 
        r"\bdelete\b", r"\bmake\s+it\b", r"\bchange\b", r"\bthe\b", 
        r"\b a\b", r"\bto\b", r"\bmy\b", r"\bcart\b"
    ]
    
    for pattern in phrases:
        cleaned = re.sub(pattern, " ", cleaned)
    
    # Clean up whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def extract_quantity(msg: str) -> Optional[int]:
    """Extract quantity number from message."""
    import re
    numbers = re.findall(r'\d+', msg)
    if numbers:
        qty = int(numbers[0])
        return qty if 1 <= qty <= 100 else 1  # Sanity check
    return 1


def extract_price(search_result: str) -> int:
    """Extract price from search tool results."""
    import re
    
    # Look for Naira symbol followed by numbers
    prices = re.findall(r'₦\s*([\d,]+)', search_result)
    
    if prices:
        # Take first price found, remove commas, convert to int
        price_str = prices[0].replace(',', '')
        return int(price_str)
    
    # Fallback: look for just numbers after common price indicators
    if "price" in search_result.lower():
        numbers = re.findall(r'(\d+,?\d*)', search_result)
        if numbers:
            return int(numbers[0].replace(',', ''))
    
    # No price found
    return 0


def extract_product_from_search(search_result: str, requested_name: str) -> dict:
    """
    Extract product details from search results and validate it matches the request.
    
    Returns:
        dict with 'name' and 'price' if valid product found, None otherwise
    """
    import re
    
    # Check if search returned "No results" or error
    if not search_result or "no results" in search_result.lower() or "not found" in search_result.lower():
        return None
    
    # Extract product name and price from search result
    # Format: "Name: Product Name\nPrice: ₦X,XXX" or "**Product Name** at ₦X,XXX"
    
    # Try pattern 1: Name: ... Price: ₦...
    name_match = re.search(r'Name:\s*([^\n]+)', search_result)
    price_match = re.search(r'(?:Price|₦)\s*([\d,]+)', search_result)
    
    if name_match and price_match:
        found_name = name_match.group(1).strip()
        price_str = price_match.group(1).replace(',', '')
        price = int(price_str)
        
        # Validate: check if found product name reasonably matches requested name
        # Use fuzzy matching - check if key words overlap
        requested_words = set(requested_name.lower().split())
        found_words = set(found_name.lower().split())
        
        # At least 50% word overlap or exact substring match
        overlap = len(requested_words & found_words) / max(len(requested_words), 1)
        substring_match = requested_name.lower() in found_name.lower() or found_name.lower() in requested_name.lower()
        
        if overlap >= 0.5 or substring_match:
            return {"name": found_name, "price": price}
    
    # No valid match found
    return None

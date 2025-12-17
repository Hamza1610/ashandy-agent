"""
Order Parser: Extracts order details from conversation history.
Parses sales agent messages to identify products, quantities, and prices.
"""
import re
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def extract_order_items(messages: list) -> List[Dict]:
    """
    Extract ordered items from conversation messages.
    
    Looks for:
    - Product names mentioned
    - Prices (₦xxx or Nxxx format)
    - Quantities (if mentioned)
    - Tool call results from product search
    
    Args:
        messages: List of conversation messages
        
    Returns:
        List of order items: [{"name": "...", "price": float, "quantity": int}]
    """
    logger.debug(f"Extracting order items from {len(messages)} messages")
    
    order_items = []
    
    for msg in messages:
        # Check tool messages (product search results)
        if hasattr(msg, 'type') and msg.type == 'tool':
            content = msg.content if hasattr(msg, 'content') else str(msg)
            items = parse_product_list(content)
            if items:
                order_items.extend(items)
                logger.debug(f"Found {len(items)} items in tool message")
        
        # Check AI messages for product mentions
        elif hasattr(msg, 'content'):
            content = msg.content
            items = parse_ai_message(content)
            if items:
                order_items.extend(items)
                logger.debug(f"Found {len(items)} items in AI message")
    
    consolidated = consolidate_items(order_items)
    logger.info(f"Extracted {len(consolidated)} unique order items")
    
    return consolidated


def parse_product_list(text: str) -> List[Dict]:
    """
    Parse product list from tool output.
    
    Format:
        - ID: 123
          Name: Product Name
          Price: ₦10,000
          Stock: 5
    """
    items = []
    
    pattern = r'Name:\s*(.+?)\s*(?:Pr(?:ice)?:?\s*₦?([\d,]+))?'
    matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        name = match.group(1).strip()
        price_str = match.group(2)
        
        if not name or name.lower() in ['none', 'n/a', '']:
            continue
        
        price = 0.0
        if price_str:
            price = float(price_str.replace(',', ''))
        
        items.append({
            "name": name,
            "price": price,
            "quantity": 1
        })
    
    return items


def parse_ai_message(text: str) -> List[Dict]:
    """
    Parse product mentions from AI messages.
    
    Looks for patterns like:
    - "Product Name - ₦10,000"
    - "Product Name (₦10,000)"
    - "₦10,000 for Product Name"
    """
    items = []
    
    pattern1 = r'([A-Z][A-Za-z\s]+?)\s*[-–(]\s*₦?([\d,]+)\)?'
    matches1 = re.finditer(pattern1, text)
    
    for match in matches1:
        name = match.group(1).strip()
        price_str = match.group(2)
        
        if len(name) > 3:
            price = float(price_str.replace(',', ''))
            items.append({
                "name": name,
                "price": price,
                "quantity": 1
            })
    
    return items


def consolidate_items(items: List[Dict]) -> List[Dict]:
    """Consolidate duplicate items and sum quantities."""
    if not items:
        return []
    
    consolidated = {}
    
    for item in items:
        name = item["name"]
        price = item["price"]
        quantity = item.get("quantity", 1)
        
        if name in consolidated:
            consolidated[name]["quantity"] += quantity
        else:
            consolidated[name] = {
                "name": name,
                "price": price,
                "quantity": quantity
            }
    
    return list(consolidated.values())


def calculate_total(items: List[Dict], transport_fee: float = 500.0) -> Dict:
    """
    Calculate order total with transport fee.
    
    Args:
        items: List of order items
        transport_fee: Delivery fee (default ₦500)
        
    Returns:
        {"items_total": float, "transport_fee": float, "total": float, "item_count": int}
    """
    items_total = sum(item["price"] * item.get("quantity", 1) for item in items)
    total = items_total + transport_fee
    
    return {
        "items_total": items_total,
        "transport_fee": transport_fee,
        "total": total,
        "item_count": len(items)
    }


def format_items_summary(items: List[Dict]) -> str:
    """
    Format items for SMS/display.
    
    Returns:
        "2x Red Lipstick (₦3,500 each)
         1x Foundation (₦5,000)"
    """
    lines = []
    for item in items:
        qty = item.get("quantity", 1)
        name = item["name"]
        price = item["price"]
        
        lines.append(f"{qty}x {name} (₦{price:,.0f} each)")
    
    return "\n".join(lines)


def extract_customer_email(messages: list, state: dict) -> Optional[str]:
    """
    Extract customer email from conversation or state.
    
    Priority:
    1. State customer_email field
    2. Email mentioned in recent HumanMessages (user input)
    3. None
    """
    # Check state first
    if state.get("customer_email"):
        return state["customer_email"]
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Search recent messages (last 10) for email
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    
    for msg in reversed(recent_messages):
        msg_type = getattr(msg, 'type', None)
        content = getattr(msg, 'content', None)
        
        if content and isinstance(content, str):
            if msg_type == 'human' or msg_type is None:
                match = re.search(email_pattern, content)
                if match:
                    logger.debug(f"Found customer email: {match.group(0)}")
                    return match.group(0)
    
    return None

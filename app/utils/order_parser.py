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
    print(f"\n>>> ORDER PARSER: Analyzing {len(messages)} messages")
    logger.info(f"Extracting order items from {len(messages)} messages")
    
    order_items = []
    
    # Track products mentioned in conversation
    for msg in messages:
        # Check tool messages (product search results)
        if hasattr(msg, 'type') and msg.type == 'tool':
            content = msg.content if hasattr(msg, 'content') else str(msg)
            items = parse_product_list(content)
            if items:
                order_items.extend(items)
                print(f">>> ORDER PARSER: Found {len(items)} items in tool message")
        
        # Check AI messages for product mentions
        elif hasattr(msg, 'content'):
            content = msg.content
            # Look for price patterns in AI responses
            items = parse_ai_message(content)
            if items:
                order_items.extend(items)
                print(f">>> ORDER PARSER: Found {len(items)} items in AI message")
    
    # Deduplicate and consolidate
    consolidated = consolidate_items(order_items)
    
    print(f">>> ORDER PARSER: Extracted {len(consolidated)} unique items")
    for item in consolidated:
        print(f">>> ORDER PARSER: - {item['name']} x{item['quantity']} @ ₦{item['price']:,.0f}")
    
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
    
    # Pattern: Name: ... Price: ₦... (with optional commas)
    pattern = r'Name:\s*(.+?)\s*(?:Pr(?:ice)?:?\s*₦?([\d,]+))?'
    matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        name = match.group(1).strip()
        price_str = match.group(2)
        
        if not name or name.lower() in ['none', 'n/a', '']:
            continue
        
        # Parse price
        price = 0.0
        if price_str:
            price = float(price_str.replace(',', ''))
        
        items.append({
            "name": name,
            "price": price,
            "quantity": 1  # Default quantity
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
    
    # Pattern 1: Name - ₦Price or Name (₦Price)
    pattern1 = r'([A-Z][A-Za-z\s]+?)\s*[-–(]\s*₦?([\d,]+)\)?'
    matches1 = re.finditer(pattern1, text)
    
    for match in matches1:
        name = match.group(1).strip()
        price_str = match.group(2)
        
        if len(name) > 3:  # Avoid single words
            price = float(price_str.replace(',', ''))
            items.append({
                "name": name,
                "price": price,
                "quantity": 1
            })
    
    return items


def consolidate_items(items: List[Dict]) -> List[Dict]:
    """
    Consolidate duplicate items and sum quantities.
    """
    if not items:
        return []
    
    # Group by name
    consolidated = {}
    
    for item in items:
        name = item["name"]
        price = item["price"]
        quantity = item.get("quantity", 1)
        
        if name in consolidated:
            # If same product, add quantity
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
        {
            "items_total": float,
            "transport_fee": float,
            "total": float,
            "item_count": int
        }
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
    print(f"\n>>> EMAIL PARSER: Starting extraction from {len(messages)} messages")
    
    # Check state first
    if state.get("customer_email"):
        email = state["customer_email"]
        print(f">>> EMAIL PARSER: Found in state: {email}")
        return email
    
    print(f">>> EMAIL PARSER: No email in state, searching messages...")
    
    # Email regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Search recent messages (last 10) for email - focusing on HumanMessages
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    print(f">>> EMAIL PARSER: Checking last {len(recent_messages)} messages")
    
    for i, msg in enumerate(reversed(recent_messages)):
        # Check if it's a HumanMessage (user input)
        msg_type = getattr(msg, 'type', None)
        content = getattr(msg, 'content', None)
        
        print(f">>> EMAIL PARSER: Message {i}: type={msg_type}, has_content={content is not None}")
        
        if content and isinstance(content, str):
            print(f">>> EMAIL PARSER: Content preview: {content[:80]}...")
            
            # Only search in human messages or if type not specified
            if msg_type == 'human' or msg_type is None:
                match = re.search(email_pattern, content)
                if match:
                    email = match.group(0)
                    print(f">>> EMAIL PARSER: ✓ Found in message (type={msg_type}): {email}")
                    return email
                else:
                    print(f">>> EMAIL PARSER: No email match in this message")
            else:
                print(f">>> EMAIL PARSER: Skipping (type={msg_type})")
    
    print(f">>> EMAIL PARSER: ❌ No email found in any messages")
    return None

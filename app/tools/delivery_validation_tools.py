"""
Tools for collecting and validating delivery details before payment.
"""
from langchain_core.tools import tool
import logging
import re

logger = logging.getLogger(__name__)

# Fallback email for Paystack
DEFAULT_EMAIL = "ashandyawelewa@gmail.com"


def validate_nigerian_phone(phone: str) -> str:
    """
    Validate and normalize Nigerian phone number.
    Returns normalized format or None if invalid.
    """
    if not phone:
        return None
    
    # Remove spaces, dashes, and other characters
    clean = re.sub(r'[^\d+]', '', phone)
    
    # Handle various formats
    if clean.startswith('+234'):
        normalized = clean
    elif clean.startswith('234'):
        normalized = '+' + clean
    elif clean.startswith('0') and len(clean) == 11:
        normalized = '+234' + clean[1:]
    elif len(clean) == 10:
        normalized = '+234' + clean
    else:
        return None  # Invalid
    
    # Validate length
    if len(normalized) != 14:
        return None
    
    return normalized


def validate_delivery_details(details: dict) -> dict:
    """
    Validate delivery details and return missing fields.
    
    Required fields:
    - name (full name)
    - phone (valid Nigerian number)
    - address (street address)
    
    Optional fields:
    - city
    - state
    - email (defaults to ashandyawelewa@gmail.com)
    
    Returns:
        dict with 'valid' bool and 'missing' list
    """
    missing = []
    warnings = []
    
    # Check name
    name = details.get('name', '').strip()
    if not name or len(name) < 3:
        missing.append('full name')
    
    # Check phone
    phone = details.get('phone', '').strip()
    normalized_phone = validate_nigerian_phone(phone)
    if not normalized_phone:
        missing.append('phone number')
    else:
        details['phone'] = normalized_phone
    
    # Check address
    address = details.get('address', '').strip()
    if not address or len(address) < 5:
        missing.append('delivery address')
    
    # Email - use fallback if not provided
    email = details.get('email', '').strip()
    if not email or '@' not in email:
        details['email'] = DEFAULT_EMAIL
        warnings.append(f"Using default email: {DEFAULT_EMAIL}")
    
    return {
        'valid': len(missing) == 0,
        'missing': missing,
        'warnings': warnings,
        'details': details
    }


@tool
async def request_delivery_details() -> str:
    """
    Request delivery details from the customer.
    
    Use this BEFORE generating a payment link when delivery details are needed.
    
    Returns:
        Message asking customer for delivery information
    """
    logger.info("Requesting delivery details from customer")
    
    return """To complete your order, please provide your delivery details:

📝 **Full Name:**
📞 **Phone Number:**
📍 **Delivery Address:**
🏙️ **City:**
📧 **Email (optional):**

Example:
"John Doe, 08012345678, 15 Admiralty Way Lekki, Lagos"
"""


@tool
async def validate_and_extract_delivery(message: str) -> dict:
    """
    Extract and validate delivery details from a customer message.
    
    Args:
        message: Customer's message containing delivery info
    
    Returns:
        dict with extracted details and validation status
    """
    logger.info(f"Extracting delivery details from: {message[:100]}...")
    
    result = {
        'name': None,
        'phone': None,
        'address': None,
        'city': None,
        'state': None,
        'email': DEFAULT_EMAIL
    }
    
    # Extract phone number
    phone_patterns = [
        r'\+234\d{10}',
        r'234\d{10}',
        r'0[789]\d{9}',
        r'0[789]\d{2}[\s-]?\d{3}[\s-]?\d{4}'
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, message)
        if match:
            result['phone'] = match.group(0)
            break
    
    # Extract email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
    if email_match:
        result['email'] = email_match.group(0)
    
    # Extract address (heuristics - look for common patterns)
    # Remove phone and email first
    clean_msg = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', message)
    clean_msg = re.sub(r'\+?234?\d{10,11}', '', clean_msg)
    clean_msg = re.sub(r'0[789]\d{9}', '', clean_msg)
    
    # Split by comma and analyze
    parts = [p.strip() for p in clean_msg.split(',') if p.strip()]
    
    if len(parts) >= 2:
        # First part likely name
        potential_name = parts[0]
        if len(potential_name) > 2 and not re.search(r'\d', potential_name):
            result['name'] = potential_name
        
        # Middle parts likely address
        if len(parts) >= 3:
            result['address'] = ', '.join(parts[1:-1])
            result['city'] = parts[-1]
        elif len(parts) == 2:
            result['address'] = parts[1]
    
    # Validate
    validation = validate_delivery_details(result)
    
    return {
        'extracted': result,
        'valid': validation['valid'],
        'missing': validation['missing'],
        'warnings': validation['warnings']
    }


@tool
async def check_delivery_ready(order_data: dict) -> dict:
    """
    Check if order has all required delivery details before payment.
    
    Args:
        order_data: Order data extracted from conversation
    
    Returns:
        dict with 'ready' bool and 'missing' list
    """
    delivery = order_data.get('delivery_details', {})
    
    if order_data.get('delivery_type', '').lower() == 'pickup':
        # Pickup only needs name and phone
        if delivery.get('name') and delivery.get('phone'):
            return {'ready': True, 'missing': []}
        
        missing = []
        if not delivery.get('name'):
            missing.append('name')
        if not delivery.get('phone'):
            missing.append('phone')
        return {'ready': False, 'missing': missing}
    
    # Delivery needs full details
    validation = validate_delivery_details(delivery)
    
    return {
        'ready': validation['valid'],
        'missing': validation['missing'],
        'email': validation['details'].get('email', DEFAULT_EMAIL)
    }

"""
Delivery Validation Tools: Collect and validate delivery details before payment.
"""
from langchain_core.tools import tool
import logging
import re

logger = logging.getLogger(__name__)
DEFAULT_EMAIL = "ashandyawelewa@gmail.com"


def validate_nigerian_phone(phone: str) -> str:
    """Validate and normalize Nigerian phone number. Returns normalized or None."""
    if not phone:
        return None
    clean = re.sub(r'[^\d+]', '', phone)
    
    if clean.startswith('+234'):
        normalized = clean
    elif clean.startswith('234'):
        normalized = '+' + clean
    elif clean.startswith('0') and len(clean) == 11:
        normalized = '+234' + clean[1:]
    elif len(clean) == 10:
        normalized = '+234' + clean
    else:
        return None
    
    return normalized if len(normalized) == 14 else None


def validate_delivery_details(details: dict) -> dict:
    """Validate delivery details. Returns {valid, missing, warnings, details}."""
    missing, warnings = [], []
    
    if not details.get('name', '').strip() or len(details.get('name', '')) < 3:
        missing.append('full name')
    
    normalized_phone = validate_nigerian_phone(details.get('phone', ''))
    if not normalized_phone:
        missing.append('phone number')
    else:
        details['phone'] = normalized_phone
    
    if not details.get('address', '').strip() or len(details.get('address', '')) < 5:
        missing.append('delivery address')
    
    if not details.get('email') or '@' not in details.get('email', ''):
        details['email'] = DEFAULT_EMAIL
        warnings.append(f"Using default email: {DEFAULT_EMAIL}")
    
    return {'valid': len(missing) == 0, 'missing': missing, 'warnings': warnings, 'details': details}


@tool
async def request_delivery_details() -> str:
    """Request delivery details from customer."""
    logger.info("Requesting delivery details")
    return """To complete your order, please provide:

📝 **Full Name:**
📞 **Phone Number:**
📍 **Delivery Address:**
🏙️ **City:**
📧 **Email (optional):**

Example: "John Doe, 08012345678, 15 Admiralty Way Lekki, Lagos"
"""


@tool
async def validate_and_extract_delivery(message: str) -> dict:
    """Extract and validate delivery details from customer message."""
    logger.info(f"Extracting from: {message[:100]}...")
    
    result = {'name': None, 'phone': None, 'address': None, 'city': None, 'state': None, 'email': DEFAULT_EMAIL}
    
    # Extract phone
    for pattern in [r'\+234\d{10}', r'234\d{10}', r'0[789]\d{9}', r'0[789]\d{2}[\s-]?\d{3}[\s-]?\d{4}']:
        match = re.search(pattern, message)
        if match:
            result['phone'] = match.group(0)
            break
    
    # Extract email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
    if email_match:
        result['email'] = email_match.group(0)
    
    # Extract address
    clean_msg = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', message)
    clean_msg = re.sub(r'\+?234?\d{10,11}', '', clean_msg)
    clean_msg = re.sub(r'0[789]\d{9}', '', clean_msg)
    
    parts = [p.strip() for p in clean_msg.split(',') if p.strip()]
    if len(parts) >= 2:
        if len(parts[0]) > 2 and not re.search(r'\d', parts[0]):
            result['name'] = parts[0]
        if len(parts) >= 3:
            result['address'] = ', '.join(parts[1:-1])
            result['city'] = parts[-1]
        elif len(parts) == 2:
            result['address'] = parts[1]
    
    validation = validate_delivery_details(result)
    return {'extracted': result, 'valid': validation['valid'], 'missing': validation['missing'], 'warnings': validation['warnings']}


@tool
async def check_delivery_ready(order_data: dict) -> dict:
    """Check if order has required delivery details before payment."""
    delivery = order_data.get('delivery_details', {})
    
    if order_data.get('delivery_type', '').lower() == 'pickup':
        missing = []
        if not delivery.get('name'):
            missing.append('name')
        if not delivery.get('phone'):
            missing.append('phone')
        return {'ready': len(missing) == 0, 'missing': missing}
    
    validation = validate_delivery_details(delivery)
    return {'ready': validation['valid'], 'missing': validation['missing'], 'email': validation['details'].get('email', DEFAULT_EMAIL)}

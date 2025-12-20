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
    
    # Fix: Handle None values safely
    name = details.get('name') or ''
    if not name.strip() or len(name) < 3:
        missing.append('full name')
    
    normalized_phone = validate_nigerian_phone(details.get('phone'))
    if not normalized_phone:
        missing.append('phone number')
    else:
        details['phone'] = normalized_phone
    
    # Fix: Handle None address safely
    address = details.get('address') or ''
    if not address.strip() or len(address) < 5:
        missing.append('delivery address')
    
    # ENHANCED: Proper email validation
    email = details.get('email')
    if not email or not _validate_email_format(email):
        details['email'] = DEFAULT_EMAIL
        warnings.append(f"Invalid/missing email, using default: {DEFAULT_EMAIL}")
    
    return {'valid': len(missing) == 0, 'missing': missing, 'warnings': warnings, 'details': details}


def _validate_email_format(email: str) -> bool:
    """
    Validate email format using RFC-compliant regex.
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid email format
    """
    if not email or len(email) > 255:
        return False
    
    # RFC 5321 compliant email regex
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@'  # Local part (max 64 chars)
        r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.'     # Domain
        r'[a-zA-Z]{2,}$'                          # TLD (min 2 chars)
    )
    
    if not EMAIL_REGEX.match(email):
        return False
    
    # Additional checks
    if email.count('@') != 1:
        return False
    
    local, domain = email.split('@')
    if len(local) > 64:
        return False
    
    return True



@tool
async def request_delivery_details() -> str:
    """Request delivery details from customer."""
    logger.info("Requesting delivery details")
    return """To complete your order, please provide details (one by one is okay):

📝 **Name**
📞 **Phone**
📍 **Address** (include city)

Example: "My name is John Doe", "08012345678", or "15 Admiralty Way, Lekki"
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
    
    # Extract potential name/address using simple heuristics
    # Remove phone and email to see what's left
    clean_msg = message
    if result['phone']:
        clean_msg = clean_msg.replace(result['phone'], '')
    if result.get('email'):
        clean_msg = clean_msg.replace(result['email'], '')
    
    # Keyword removal
    clean_msg = re.sub(r'(my name is|i am|this is|call me|deliver to|address is)', '', clean_msg, flags=re.IGNORECASE)
    
    # Split by commas or newlines
    parts = [p.strip() for p in re.split(r'[,\n]', clean_msg) if p.strip()]
    
    if len(parts) >= 1:
        # Heuristic: If it looks like a name (2-3 words, no numbers), assume name if missing
        first_part = parts[0]
        if not result['name'] and 3 < len(first_part) < 30 and not re.search(r'\d', first_part):
             result['name'] = first_part
             # If there are more parts, assume address
             if len(parts) > 1:
                 result['address'] = ', '.join(parts[1:])
        elif not result['address']:
             result['address'] = ', '.join(parts)

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

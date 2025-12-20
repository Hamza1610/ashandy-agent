"""
Input Validation Utilities: Length checks and validation for all user inputs.

Prevents: Buffer overflow, DoS attacks, database overflow, memory exhaustion
AWS EC2 Compatible: Pure Python, no external dependencies
"""
import logging

logger = logging.getLogger(__name__)

# Maximum lengths (conservative, tested values)
MAX_MESSAGE_LENGTH = 10000      # ~2500 tokens, handles long product lists
MAX_NAME_LENGTH = 100           # Sufficient for full names
MAX_ADDRESS_LENGTH = 500        # Multi-line addresses with landmarks
MAX_PHONE_LENGTH = 20           # International format with spaces
MAX_EMAIL_LENGTH = 255          # RFC 5321 standard
MAX_PRODUCT_QUERY_LENGTH = 200  # Product search queries
MAX_INCIDENT_LENGTH = 2000      # Support incident descriptions
MAX_NOTES_LENGTH = 1000         # Order notes, payment notes


def validate_input_length(
    value: str, 
    max_length: int, 
    field_name: str = "Input",
    truncate: bool = False
) -> tuple[bool, str, str]:
    """
    Validate input length with optional truncation.
    
    Args:
        value: Input string to validate
        max_length: Maximum allowed length
        field_name: Name of field for error messages
        truncate: If True, truncate and return truncated value
    
    Returns:
        Tuple of (is_valid, processed_value, warning_message)
        - If valid: (True, original_value, "")
        - If invalid and truncate=False: (False, original_value, error_msg)
        - If invalid and truncate=True: (True, truncated_value, warning_msg)
    
    Example:
        >>> valid, value, msg = validate_input_length("Hello", 10, "Name")
        >>> print(valid, value, msg)
        True, "Hello", ""
        
        >>> valid, value, msg = validate_input_length("A"*1000, 100, "Name", truncate=True)
        >>> print(valid, len(value), msg)
        True, 103, "Name truncated from 1000 to 100 characters"
    """
    if not value:
        return True, value, ""
    
    current_length = len(value)
    
    if current_length <= max_length:
        return True, value, ""
    
    # Input exceeds max length
    if truncate:
        truncated = value[:max_length] + "..."
        warning = f"{field_name} truncated from {current_length} to {max_length} characters"
        logger.info(f"✂️ {warning}")
        return True, truncated, warning
    else:
        error = f"{field_name} exceeds maximum length of {max_length} characters (got {current_length})"
        logger.warning(f"⚠️ {error}")
        return False, value, error


def validate_message_length(message: str, truncate: bool = True) -> tuple[bool, str, str]:
    """
    Validate message content length.
    
    Args:
        message: User message content
        truncate: If True, automatically truncate long messages
    
    Returns:
        (is_valid, processed_message, warning)
    """
    return validate_input_length(message, MAX_MESSAGE_LENGTH, "Message", truncate)


def validate_name_length(name: str) -> tuple[bool, str, str]:
    """Validate name field length (no truncation)."""
    return validate_input_length(name, MAX_NAME_LENGTH, "Name", truncate=False)


def validate_address_length(address: str) -> tuple[bool, str, str]:
    """Validate address field length (no truncation)."""
    return validate_input_length(address, MAX_ADDRESS_LENGTH, "Address", truncate=False)


def validate_email_length(email: str) -> tuple[bool, str, str]:
    """Validate email length."""
    return validate_input_length(email, MAX_EMAIL_LENGTH, "Email", truncate=False)


def validate_phone_length(phone: str) -> tuple[bool, str, str]:
    """Validate phone number length."""
    return validate_input_length(phone, MAX_PHONE_LENGTH, "Phone", truncate=False)


def validate_product_query_length(query: str, truncate: bool = True) -> tuple[bool, str, str]:
    """Validate product search query length."""
    return validate_input_length(query, MAX_PRODUCT_QUERY_LENGTH, "Product query", truncate)


def validate_all_inputs(data: dict) -> dict:
    """
    Validate multiple inputs at once.
    
    Args:
        data: Dictionary of field_name: value pairs
    
    Returns:
        {
            'valid': bool,
            'errors': list of error messages,
            'warnings': list of warnings,
            'sanitized': dict of processed values
        }
    """
    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'sanitized': {}
    }
    
    # Field-specific validators
    validators = {
        'message': lambda v: validate_message_length(v, truncate=True),
        'name': validate_name_length,
        'address': validate_address_length,
        'email': validate_email_length,
        'phone': validate_phone_length,
        'product_query': lambda v: validate_product_query_length(v, truncate=True),
    }
    
    for field_name, value in data.items():
        if not value:
            result['sanitized'][field_name] = value
            continue
        
        # Get validator or use generic
        validator = validators.get(field_name)
        if validator:
            valid, processed, msg = validator(value)
        else:
            # Generic validation with 500 char limit
            valid, processed, msg = validate_input_length(value, 500, field_name)
        
        result['sanitized'][field_name] = processed
        
        if not valid:
            result['valid'] = False
            result['errors'].append(msg)
        elif msg:  # Warning
            result['warnings'].append(msg)
    
    return result


# Convenience function for webhooks
def validate_webhook_message(message: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """
    Validate and truncate webhook message if needed.
    Always returns valid string (truncated if necessary).
    
    Args:
        message: Raw message from webhook
        max_length: Maximum length (default: MAX_MESSAGE_LENGTH)
    
    Returns:
        Validated message (truncated if needed)
    """
    if not message:
        return ""
    
    if len(message) <= max_length:
        return message
    
    truncated = message[:max_length] + "... [Message truncated for safety]"
    logger.warning(f"⚠️ Webhook message truncated: {len(message)} → {max_length} chars")
    return truncated

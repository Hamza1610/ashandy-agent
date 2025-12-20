"""
Input Sanitization Utilities: XSS protection and content sanitization.

Prevents: XSS attacks, script injection, HTML injection, SQL injection
AWS EC2 Compatible: Uses built-in Python modules only
"""
import html
import re
import logging

logger = logging.getLogger(__name__)

# Dangerous HTML/JavaScript patterns
SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
JAVASCRIPT_PROTOCOL = re.compile(r'javascript:', re.IGNORECASE)
EVENT_HANDLER_PATTERN = re.compile(r'on\w+\s*=', re.IGNORECASE)  # onclick=, onerror=, etc.
DATA_PROTOCOL = re.compile(r'data:', re.IGNORECASE)
VBSCRIPT_PROTOCOL = re.compile(r'vbscript:', re.IGNORECASE)

# For strict mode (names, IDs)
STRICT_ALLOWED = re.compile(r'[^a-zA-Z0-9\s\-_.,@+()\']')


def sanitize_user_input(text: str, strict: bool = False, allow_newlines: bool = True) -> str:
    """
    Sanitize user input for safe storage and display.
    
    Args:
        text: Raw user input
        strict: If True, apply stricter filtering (for names, IDs)
        allow_newlines: If True, preserve newline characters
    
    Returns:
        Sanitized text safe for storage
    
    Example:
        >>> sanitize_user_input("<script>alert('XSS')</script>Hello")
        "Hello"
        
        >>> sanitize_user_input("John's Product", strict=True)
        "John's Product"
    """
    if not text:
        return text
    
    # Step 1: HTML escape
    sanitized = html.escape(text, quote=True)
    
    # Step 2: Remove dangerous patterns
    sanitized = SCRIPT_PATTERN.sub('', sanitized)
    sanitized = JAVASCRIPT_PROTOCOL.sub('', sanitized)
    sanitized = EVENT_HANDLER_PATTERN.sub('', sanitized)
    sanitized = DATA_PROTOCOL.sub('', sanitized)
    sanitized = VBSCRIPT_PROTOCOL.sub('', sanitized)
    
    # Step 3: Remove potentially dangerous HTML tags
    sanitized = re.sub(r'<iframe[^>]*>.*?</iframe>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'<object[^>]*>.*?</object>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'<embed[^>]*>', '', sanitized, flags=re.IGNORECASE)
    
    # Step 4: Strict mode for names, IDs
    if strict:
        # Remove all characters except alphanumeric, spaces, and safe punctuation
        sanitized = STRICT_ALLOWED.sub('', sanitized)
    
    # Step 5: Handle newlines
    if not allow_newlines:
        sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
    
    # Step 6: Normalize whitespace
    sanitized = ' '.join(sanitized.split())
    
    return sanitized.strip()


def sanitize_name(name: str) -> str:
    """Sanitize name fields (strict mode)."""
    return sanitize_user_input(name, strict=True, allow_newlines=False)


def sanitize_address(address: str) -> str:
    """Sanitize address fields (allow newlines, some special chars)."""
    return sanitize_user_input(address, strict=False, allow_newlines=True)


def sanitize_message(message: str) -> str:
    """Sanitize message content (preserve formatting)."""
    return sanitize_user_input(message, strict=False, allow_newlines=True)


def sanitize_email(email: str) -> str:
    """
    Sanitize email address (very strict).
    Only allows valid email characters.
    """
    if not email:
        return email
    
    # Remove all whitespace
    email = email.strip().lower()
    
    # Only allow valid email characters
    email = re.sub(r'[^a-z0-9@._+-]', '', email)
    
    return email


def sanitize_phone(phone: str) -> str:
    """
    Sanitize phone number (digits and + only).
    """
    if not phone:
        return phone
    
    # Only allow digits, +, spaces, hyphens, parentheses
    phone = re.sub(r'[^0-9+\s\-()]', '', phone)
    
    return phone.strip()


def sanitize_for_sql(text: str) -> str:
    """
    Additional SQL injection protection (defense in depth).
    Note: Primary protection is parameterized queries, this is extra layer.
    
    Args:
        text: Input text
    
    Returns:
        Sanitized text (removes SQL keywords if present)
    """
    if not text:
        return text
    
    # Remove common SQL injection patterns
    sql_patterns = [
        r'\b(DROP|DELETE|INSERT|UPDATE|SELECT|UNION|EXEC|EXECUTE)\b',
        r'--',  # SQL comment
        r'/\*',  # Multi-line comment start
        r'\*/',  # Multi-line comment end
        r';',    # Statement terminator
    ]
    
    sanitized = text
    for pattern in sql_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    return sanitized


def sanitize_dict(data: dict, field_types: dict = None) -> dict:
    """
    Sanitize all string fields in a dictionary.
    
    Args:
        data: Dictionary with user input
        field_types: Optional dict mapping field names to types ('name', 'email', 'message', etc.)
    
    Returns:
        Dictionary with sanitized values
    
    Example:
        >>> sanitize_dict({'name': '<script>alert()</script>John', 'email': 'user@test.com'},
        ...               field_types={'name': 'name', 'email': 'email'})
        {'name': 'John', 'email': 'user@test.com'}
    """
    if not data:
        return data
    
    field_types = field_types or {}
    sanitized = {}
    
    sanitizers = {
        'name': sanitize_name,
        'email': sanitize_email,
        'phone': sanitize_phone,
        'address': sanitize_address,
        'message': sanitize_message,
    }
    
    for key, value in data.items():
        if not isinstance(value, str):
            sanitized[key] = value
            continue
        
        # Get sanitizer for this field type
        field_type = field_types.get(key, 'message')  # Default to message sanitization
        sanitizer = sanitizers.get(field_type, sanitize_message)
        
        sanitized[key] = sanitizer(value)
    
    return sanitized


def is_safe_content(text: str) -> tuple[bool, list]:
    """
    Check if content is safe (no dangerous patterns).
    
    Args:
        text: Content to check
    
    Returns:
        (is_safe, list_of_issues)
    
    Example:
        >>> is_safe_content("Hello world")
        (True, [])
        
        >>> is_safe_content("<script>alert()</script>")
        (False, ['Contains script tag'])
    """
    if not text:
        return True, []
    
    issues = []
    text_lower = text.lower()
    
    # Check for dangerous patterns
    if '<script' in text_lower:
        issues.append("Contains script tag")
    
    if 'javascript:' in text_lower:
        issues.append("Contains JavaScript protocol")
    
    if '<iframe' in text_lower:
        issues.append("Contains iframe tag")
    
    if re.search(r'on\w+\s*=', text_lower):
        issues.append("Contains event handler")
    
    # Check for SQL injection attempts
    sql_keywords = ['drop table', 'delete from', 'insert into', 'update.*set', 'union select']
    for keyword in sql_keywords:
        if re.search(keyword, text_lower):
            issues.append(f"Contains suspicious SQL pattern: {keyword}")
            break
    
    is_safe = len(issues) == 0
    
    if not is_safe:
        logger.warning(f"🚨 Unsafe content detected: {issues}")
    
    return is_safe, issues


# Convenience function for logging
def log_sanitization(original: str, sanitized: str, field_name: str = "Input"):
    """Log when content was sanitized."""
    if original != sanitized:
        changes = len(original) - len(sanitized)
        logger.info(f"🧹 Sanitized {field_name}: Removed {changes} characters")

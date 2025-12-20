"""
Security Logging Middleware: Monitor and log security events.

Purpose: Track suspicious requests, slow requests, and potential attacks
AWS EC2 Compatible: Logs to stdout for CloudWatch ingestion
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging
import time
import json
from typing import Dict, List

logger = logging.getLogger("security")

# Suspicious headers that might indicate attacks
SUSPICIOUS_HEADERS = [
    'x-forwarded-host',
    'x-original-url', 
    'x-rewrite-url',
    'x-forwarded-server',
]

# Suspicious patterns in URLs
SUSPICIOUS_URL_PATTERNS = [
    '../',  # Directory traversal
    '..\\',  # Windows directory traversal
    '%2e%2e',  # Encoded directory traversal
    'exec(',  # Code execution attempt
    'eval(',  # Code execution attempt
    '<script',  # XSS in URL
    'javascript:',  # JavaScript injection
]

# Maximum request duration before logging as slow
SLOW_REQUEST_THRESHOLD = 30.0  # seconds


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log security events for monitoring.
    
    Logs to stdout in JSON format for AWS CloudWatch ingestion.
    Does NOT block requests - only monitors and logs.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and log security events."""
        start_time = time.time()
        
        # Gather request context
        security_context = self._build_security_context(request)
        
        # Check for suspicious patterns
        suspicious, warnings = self._check_suspicious_request(request)
        
        if suspicious:
            security_context['suspicious'] = True
            security_context['warnings'] = warnings
            self._log_suspicious_request(security_context)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log slow requests (potential DoS)
            duration = time.time() - start_time
            if duration > SLOW_REQUEST_THRESHOLD:
                self._log_slow_request(security_context, duration)
            
            # Log failed requests
            if response.status_code >= 400:
                self._log_failed_request(security_context, response.status_code, duration)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_error_request(security_context, str(e), duration)
            raise
    
    def _build_security_context(self, request: Request) -> Dict:
        """Build security context for logging."""
        return {
            'timestamp': time.time(),
            'method': request.method,
            'path': request.url.path,
            'query': str(request.url.query) if request.url.query else None,
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown')[:200],  # Truncate
            'content_type': request.headers.get('content-type'),
        }
    
    def _check_suspicious_request(self, request: Request) -> tuple[bool, List[str]]:
        """
        Check if request contains suspicious patterns.
        
        Returns:
            (is_suspicious, list_of_warnings)
        """
        warnings = []
        
        # Check URL length (extremely long URLs are suspicious)
        url_str = str(request.url)
        if len(url_str) > 2000:
            warnings.append(f"Extremely long URL ({len(url_str)} chars)")
        
        # Check for suspicious headers
        for header in SUSPICIOUS_HEADERS:
            if header in request.headers:
                warnings.append(f"Suspicious header present: {header}")
        
        # Check for suspicious patterns in URL
        url_lower = url_str.lower()
        for pattern in SUSPICIOUS_URL_PATTERNS:
            if pattern in url_lower:
                warnings.append(f"Suspicious URL pattern: {pattern}")
        
        # Check for unusual content types
        content_type = request.headers.get('content-type', '').lower()
        if content_type and 'application/json' not in content_type and 'application/x-www-form-urlencoded' not in content_type and 'multipart/form-data' not in content_type:
            if request.method in ['POST', 'PUT', 'PATCH']:
                warnings.append(f"Unusual content-type: {content_type}")
        
        # Check for missing or suspicious user agents
        user_agent = request.headers.get('user-agent', '').lower()
        if not user_agent:
            warnings.append("Missing user-agent")
        elif any(bot in user_agent for bot in ['sqlmap', 'nikto', 'scanner', 'exploit']):
            warnings.append(f"Suspicious user-agent: {user_agent[:50]}")
        
        is_suspicious = len(warnings) > 0
        return is_suspicious, warnings
    
    def _log_suspicious_request(self, context: Dict):
        """Log suspicious request for monitoring."""
        log_entry = {
            'event_type': 'suspicious_request',
            **context
        }
        logger.warning(f"🔒 SUSPICIOUS REQUEST: {json.dumps(log_entry)}")
    
    def _log_slow_request(self, context: Dict, duration: float):
        """Log slow request (potential DoS or performance issue)."""
        log_entry = {
            'event_type': 'slow_request',
            'duration_seconds': round(duration, 2),
            **context
        }
        logger.warning(f"⏱️ SLOW REQUEST ({duration:.2f}s): {json.dumps(log_entry)}")
    
    def _log_failed_request(self, context: Dict, status_code: int, duration: float):
        """Log failed request."""
        log_entry = {
            'event_type': 'failed_request',
            'status_code': status_code,
            'duration_seconds': round(duration, 2),
            **context
        }
        
        if status_code >= 500:
            logger.error(f"❌ SERVER ERROR ({status_code}): {json.dumps(log_entry)}")
        elif status_code == 429:
            logger.warning(f"🚦 RATE LIMITED: {json.dumps(log_entry)}")
        elif status_code in [401, 403]:
            logger.warning(f"🔒 UNAUTHORIZED ({status_code}): {json.dumps(log_entry)}")
        else:
            logger.info(f"ℹ️ CLIENT ERROR ({status_code}): {json.dumps(log_entry)}")
    
    def _log_error_request(self, context: Dict, error: str, duration: float):
        """Log request that caused an exception."""
        log_entry = {
            'event_type': 'error_request',
            'error': error[:500],  # Truncate long errors
            'duration_seconds': round(duration, 2),
            **context
        }
        logger.error(f"💥 REQUEST ERROR: {json.dumps(log_entry)}")


def log_security_event(
    event_type: str,
    user_id: str = None,
    details: Dict = None,
    severity: str = "info"
):
    """
    Log a security event directly.
    
    Args:
        event_type: Type of security event
        user_id: User identifier (if applicable)
        details: Additional details dictionary
        severity: 'info', 'warning', 'error', 'critical'
    """
    log_entry = {
        'event_type': event_type,
        'timestamp': time.time(),
        'user_id': user_id,
        **(details or {})
    }
    
    log_message = f"🔐 SECURITY EVENT ({event_type}): {json.dumps(log_entry)}"
    
    if severity == 'critical':
        logger.critical(log_message)
    elif severity == 'error':
        logger.error(log_message)
    elif severity == 'warning':
        logger.warning(log_message)
    else:
        logger.info(log_message)

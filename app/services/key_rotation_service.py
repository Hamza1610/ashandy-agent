"""
API Key Rotation Service: Manages versioned API keys for secure rotation.

Usage:
    1. Set current and next keys in .env:
       LLAMA_API_KEY=current_key
       LLAMA_API_KEY_NEXT=new_key_for_rotation
       
    2. When rotating, swap the values and clear _NEXT
    
    3. Call key_rotation_service.check_and_rotate() periodically
"""
from app.utils.config import settings
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class KeyRotationService:
    """Manages API key rotation with versioning support."""
    
    # Maps service name to (current_key_attr, next_key_attr)
    KEY_PAIRS = {
        "groq": ("LLAMA_API_KEY", "LLAMA_API_KEY_NEXT"),
        "together": ("TOGETHER_API_KEY", "TOGETHER_API_KEY_NEXT"),
        "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_NEXT"),
        "paystack": ("PAYSTACK_SECRET_KEY", "PAYSTACK_SECRET_KEY_NEXT"),
        "pinecone": ("PINECONE_API_KEY", "PINECONE_API_KEY_NEXT"),
        "meta": ("META_WHATSAPP_TOKEN", "META_WHATSAPP_TOKEN_NEXT"),
    }
    
    def __init__(self):
        self.rotation_log = []
    
    def get_current_key(self, service: str) -> str | None:
        """Get the current key for a service."""
        if service not in self.KEY_PAIRS:
            return None
        current_attr, _ = self.KEY_PAIRS[service]
        return getattr(settings, current_attr, None)
    
    def get_next_key(self, service: str) -> str | None:
        """Get the next (rotation) key for a service."""
        if service not in self.KEY_PAIRS:
            return None
        _, next_attr = self.KEY_PAIRS[service]
        # Read from environment since it's not in settings by default
        return os.getenv(next_attr)
    
    def has_pending_rotation(self, service: str) -> bool:
        """Check if a service has a pending key rotation."""
        next_key = self.get_next_key(service)
        current_key = self.get_current_key(service)
        return bool(next_key and next_key != current_key)
    
    def get_rotation_status(self) -> dict:
        """Get rotation status for all services."""
        status = {}
        for service in self.KEY_PAIRS:
            current = self.get_current_key(service)
            next_key = self.get_next_key(service)
            
            status[service] = {
                "configured": bool(current),
                "current_key_suffix": current[-4:] if current else None,
                "next_key_pending": bool(next_key and next_key != current),
                "next_key_suffix": next_key[-4:] if next_key else None,
            }
        return status
    
    def log_rotation_event(self, service: str, event: str):
        """Log a key rotation event."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": service,
            "event": event
        }
        self.rotation_log.append(entry)
        logger.info(f"Key Rotation: {service} - {event}")
    
    def rotate_key(self, service: str) -> bool:
        """
        Perform key rotation for a service.
        
        In production, this would:
        1. Update environment variables
        2. Reload settings
        3. Verify new key works
        4. Clear the NEXT key
        
        For now, logs the rotation intent.
        """
        if not self.has_pending_rotation(service):
            logger.warning(f"No pending rotation for {service}")
            return False
        
        current = self.get_current_key(service)
        next_key = self.get_next_key(service)
        
        self.log_rotation_event(
            service,
            f"Rotation requested: ...{current[-4:] if current else 'None'} -> ...{next_key[-4:]}"
        )
        
        # In practice, you would:
        # 1. Test the new key
        # 2. Update .env or secrets manager
        # 3. Restart the service or hot-reload settings
        
        logger.info(f"Key rotation for {service} logged. Manual update required.")
        return True


# Singleton instance
key_rotation_service = KeyRotationService()

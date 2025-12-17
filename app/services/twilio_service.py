"""
Twilio Service: WhatsApp messaging via Twilio API.
"""
import logging
from typing import Optional
from app.utils.config import settings

logger = logging.getLogger(__name__)

class TwilioService:
    """Handles WhatsApp messaging via Twilio API."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Twilio client."""
        if not self._client:
            if self.account_sid and self.auth_token:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            else:
                logger.error("Twilio credentials not configured")
        return self._client
        
    def _format_whatsapp_number(self, phone: str) -> str:
        """Ensure phone number is in whatsapp:+ Format."""
        if not phone:
            return ""
        
        clean = phone.strip()
        # Basic normalization for Nigeria (specific to this project context based on observed code)
        if clean.startswith("0") and len(clean) == 11:
            clean = "+234" + clean[1:]
            
        if not clean.startswith("whatsapp:"):
            return f"whatsapp:{clean}"
        return clean
        
    def _get_from_number(self) -> str:
        """Get formatted from number."""
        if not self.from_number:
            return ""
        if not self.from_number.startswith("whatsapp:"):
            return f"whatsapp:{self.from_number}"
        return self.from_number

    async def send_whatsapp_text(self, to_phone: str, text: str):
        """Send text message via Twilio WhatsApp."""
        if not self.client:
            return {"status": "error", "provider": "twilio", "error": "Twilio not configured"}

        try:
            from_num = self._get_from_number()
            to_num = self._format_whatsapp_number(to_phone)
            
            message = self.client.messages.create(
                body=text,
                from_=from_num,
                to=to_num
            )
            return {"status": "sent_via_twilio", "provider": "twilio", "sid": message.sid}
        except Exception as e:
            logger.error(f"Twilio send text failed: {e}")
            return {"status": "error", "provider": "twilio", "error": str(e)}

    async def send_whatsapp_image(self, to_phone: str, image_url: str, caption: str = ""):
        """Send image message via Twilio WhatsApp."""
        if not self.client:
            return {"status": "error", "provider": "twilio", "error": "Twilio not configured"}

        try:
            from_num = self._get_from_number()
            to_num = self._format_whatsapp_number(to_phone)
            
            # Twilio handles media via media_url list
            # Note: Caption is only supported by some WhatsApp providers on Twilio but generally passed as body
            message = self.client.messages.create(
                body=caption,
                media_url=[image_url],
                from_=from_num,
                to=to_num
            )
            return {"status": "sent_via_twilio", "provider": "twilio", "sid": message.sid}
        except Exception as e:
            logger.error(f"Twilio send image failed: {e}")
            return {"status": "error", "provider": "twilio", "error": str(e)}

twilio_service = TwilioService()

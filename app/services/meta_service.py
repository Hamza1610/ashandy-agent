import httpx
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

class MetaService:
    def __init__(self):
        self.wa_token = settings.META_WHATSAPP_TOKEN
        self.wa_phone_id = settings.META_WHATSAPP_PHONE_ID
        self.ig_token = settings.META_INSTAGRAM_TOKEN
        self.ig_account_id = settings.META_INSTAGRAM_ACCOUNT_ID
        
        self.wa_url = f"https://graph.facebook.com/v18.0/{self.wa_phone_id}/messages"
        # IG Graph API for DMs: https://graph.facebook.com/v18.0/me/messages?access_token=...
        self.ig_url = "https://graph.facebook.com/v18.0/me/messages"

    async def send_whatsapp_text(self, to_phone: str, text: str):
        if not self.wa_token or not self.wa_phone_id:
            logger.error("WhatsApp credentials missing.")
            return {"error": "Missing credentials"}

        headers = {
            "Authorization": f"Bearer {self.wa_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": text}
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.wa_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API Error: {e.response.text}")
                return {"error": str(e), "details": e.response.text}
            except Exception as e:
                logger.error(f"WhatsApp send error: {e}")
                return {"error": str(e)}

    async def send_instagram_text(self, to_id: str, text: str):
        if not self.ig_token:
            logger.error("Instagram Token missing.")
            return {"error": "Missing credentials"}

        # For Instagram messaging, 'recipient' object needed
        headers = {
            "Authorization": f"Bearer {self.ig_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "recipient": {"id": to_id},
            "message": {"text": text}
        }

        async with httpx.AsyncClient() as client:
            try:
                # Assuming 'me/messages' works with Page Access Token linked to the IG account
                response = await client.post(self.ig_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Instagram API Error: {e.response.text}")
                return {"error": str(e), "details": e.response.text}
            except Exception as e:
                logger.error(f"Instagram send error: {e}")
                return {"error": str(e)}

meta_service = MetaService()

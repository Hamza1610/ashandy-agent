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
        # 1. Try Meta API First
        if self.wa_token and self.wa_phone_id:
            try:
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
                    response = await client.post(self.wa_url, headers=headers, json=payload)
                    response.raise_for_status()

                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.info("RESULT FROM AGENT:", payload)
                logger.error(f"Meta WhatsApp 401/403 Error: {e.response.text}. Token may be invalid.")
                # Proceed to fallback
            except Exception as e:
                logger.error(f"Meta WhatsApp failed: {e}. Attempting Twilio Fallback...")

        # 2. Fallback to Twilio
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
            try:
                from twilio.rest import Client
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                message = client.messages.create(
                    body=text,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
                )
                logger.info(f"Sent via Twilio: {message.sid}")
                return {"status": "sent_via_twilio", "sid": message.sid}
            except Exception as e:
                logger.error(f"Twilio Fallback failed: {e}")
                return {"error": f"All channels failed. Meta: see logs. Twilio: {e}"}
        
        return {"error": "Meta failed and Twilio credentials missing."}

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
    async def get_media_url(self, media_id: str) -> str:
        """
        Retrieve the URL for a media ID from the Graph API.
        Note: The returned URL requires an Authorization header to download.
        """
        if not self.wa_token:
            return None
            
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {self.wa_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data.get("url")
            except Exception as e:
                logger.error(f"Failed to get media URL for {media_id}: {e}")
                return None

meta_service = MetaService()

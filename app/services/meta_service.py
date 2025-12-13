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
                    data = response.json()
                    logger.info(f"Meta WhatsApp send success to {to_phone}: {data}")
                    return {"status": "sent_via_meta", "provider": "meta", "response": data}
            except httpx.HTTPStatusError as e:
                logger.error(f"Meta WhatsApp 401/403 Error: {e.response.text}. Token may be invalid.")
                # Proceed to fallback
            except Exception as e:
                logger.error(f"Meta WhatsApp failed: {e}. Attempting Twilio Fallback...")

        # 2. Fallback to Twilio
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
            try:
                from twilio.rest import Client
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                
                # Ensure 'from_' has 'whatsapp:' prefix if 'to' has it
                # Usually Twilio WhatsApp senders are "whatsapp:+14155238886"
                from_num = settings.TWILIO_PHONE_NUMBER
                if not from_num.startswith("whatsapp:"):
                    from_num = f"whatsapp:{from_num}"
                
                # Normalize 'to_phone' to E.164 if it looks like a local Nigerian number
                clean_to = to_phone.strip()
                if clean_to.startswith("0") and len(clean_to) == 11 and clean_to.isdigit():
                    clean_to = "+234" + clean_to[1:]
                
                to_num = f"whatsapp:{clean_to}" if not clean_to.startswith("whatsapp:") else clean_to

                message = client.messages.create(
                    body=text,
                    from_=from_num,
                    to=to_num
                )
                logger.info(f"Twilio WhatsApp send success to {to_phone}: sid={message.sid}")
                return {"status": "sent_via_twilio", "provider": "twilio", "sid": message.sid}
            except Exception as e:
                logger.error(f"Twilio Fallback failed: {e}")
                return {"status": "error", "provider": "twilio", "error": str(e)}
        
        return {"status": "error", "provider": "meta", "error": "Meta failed and Twilio credentials missing."}

    async def send_instagram_text(self, to_id: str, text: str):
        if not self.ig_token:
            logger.error("Instagram Token missing.")
            return {"status": "error", "provider": "instagram", "error": "Missing credentials"}

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
                data = response.json()
                logger.info(f"Instagram send success to {to_id}: {data}")
                return {"status": "sent_via_instagram", "provider": "instagram", "response": data}
            except httpx.HTTPStatusError as e:
                logger.error(f"Instagram API Error: {e.response.text}")
                return {"status": "error", "provider": "instagram", "error": str(e), "details": e.response.text}
            except Exception as e:
                logger.error(f"Instagram send error: {e}")
                return {"status": "error", "provider": "instagram", "error": str(e)}

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

    async def get_instagram_posts(self, limit: int = 10):
        """
        Fetch recent posts from the Instagram Business Account.
        Returns list of dicts: {id, caption, media_url, permalink, like_count}
        """
        if not self.ig_token or not self.ig_account_id:
            logger.error("Instagram Token or Account ID missing for post fetch.")
            return []

        url = f"https://graph.facebook.com/v18.0/{self.ig_account_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count",
            "limit": limit,
            "access_token": self.ig_token
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
            except Exception as e:
                logger.error(f"Failed to fetch IG posts: {e}")
                return []

    async def mark_whatsapp_message_read(self, message_id: str):
        """
        Mark a message as read in WhatsApp to give user instant feedback.
        """
        if not self.wa_token or not self.wa_phone_id or not message_id:
            return
            
        url = f"https://graph.facebook.com/v18.0/{self.wa_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.wa_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Fire and forget - don't block main thread too much
                await client.post(url, headers=headers, json=payload)
                logger.info(f"Marked message {message_id} as read.")
            except Exception as e:
                logger.warning(f"Failed to mark message read: {e}")

meta_service = MetaService()

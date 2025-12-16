"""
Meta Service: WhatsApp and Instagram messaging via Meta Graph API.
"""
import httpx
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)


class MetaService:
    """Handles WhatsApp and Instagram messaging via Meta APIs."""
    
    def __init__(self):
        self.wa_token = settings.META_WHATSAPP_TOKEN
        self.wa_phone_id = settings.META_WHATSAPP_PHONE_ID
        self.ig_token = settings.META_INSTAGRAM_TOKEN
        self.ig_account_id = settings.META_INSTAGRAM_ACCOUNT_ID
        self.wa_url = f"https://graph.facebook.com/v18.0/{self.wa_phone_id}/messages"
        self.ig_url = "https://graph.facebook.com/v18.0/me/messages"

    async def send_whatsapp_text(self, to_phone: str, text: str):
        """Send text message via WhatsApp. Falls back to Twilio if Meta fails."""
        if self.wa_token and self.wa_phone_id:
            try:
                headers = {"Authorization": f"Bearer {self.wa_token}", "Content-Type": "application/json"}
                payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": text}}
                async with httpx.AsyncClient() as client:
                    response = await client.post(self.wa_url, headers=headers, json=payload)
                    response.raise_for_status()
                    return {"status": "sent_via_meta", "provider": "meta", "response": response.json()}
            except httpx.HTTPStatusError as e:
                logger.error(f"Meta WhatsApp Error: {e.response.text}")
            except Exception as e:
                logger.error(f"Meta WhatsApp failed: {e}")

        # Twilio fallback
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
            try:
                from twilio.rest import Client
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                from_num = settings.TWILIO_PHONE_NUMBER
                if not from_num.startswith("whatsapp:"):
                    from_num = f"whatsapp:{from_num}"
                clean_to = to_phone.strip()
                if clean_to.startswith("0") and len(clean_to) == 11:
                    clean_to = "+234" + clean_to[1:]
                to_num = f"whatsapp:{clean_to}" if not clean_to.startswith("whatsapp:") else clean_to
                message = client.messages.create(body=text, from_=from_num, to=to_num)
                return {"status": "sent_via_twilio", "provider": "twilio", "sid": message.sid}
            except Exception as e:
                logger.error(f"Twilio Fallback failed: {e}")
                return {"status": "error", "provider": "twilio", "error": str(e)}
        
        return {"status": "error", "provider": "meta", "error": "Meta failed and Twilio not configured."}

    async def send_instagram_text(self, to_id: str, text: str):
        """Send Instagram DM."""
        if not self.ig_token:
            return {"status": "error", "provider": "instagram", "error": "Missing credentials"}

        headers = {"Authorization": f"Bearer {self.ig_token}", "Content-Type": "application/json"}
        payload = {"recipient": {"id": to_id}, "message": {"text": text}}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.ig_url, headers=headers, json=payload)
                response.raise_for_status()
                return {"status": "sent_via_instagram", "provider": "instagram", "response": response.json()}
            except Exception as e:
                logger.error(f"Instagram send error: {e}")
                return {"status": "error", "provider": "instagram", "error": str(e)}

    async def get_media_url(self, media_id: str) -> str:
        """Retrieve media URL from Graph API."""
        if not self.wa_token:
            return None
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {self.wa_token}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json().get("url")
            except Exception as e:
                logger.error(f"Failed to get media URL: {e}")
                return None

    async def get_instagram_posts(self, limit: int = 10):
        """Fetch recent Instagram posts."""
        if not self.ig_token or not self.ig_account_id:
            return []
        url = f"https://graph.facebook.com/v18.0/{self.ig_account_id}/media"
        params = {"fields": "id,caption,media_type,media_url,permalink,timestamp,like_count", "limit": limit, "access_token": self.ig_token}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json().get("data", [])
            except Exception as e:
                logger.error(f"Failed to fetch IG posts: {e}")
                return []

    async def get_instagram_media(self, media_id: str) -> Optional[dict]:
        """
        Fetch specific Instagram media details (post/story) by ID.
        Used to get context when user replies to a story or post.
        
        Returns: {id, caption, media_type, media_url, permalink} or None
        """
        if not self.ig_token or not media_id:
            return None
        
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        params = {
            "fields": "id,caption,media_type,media_url,permalink,timestamp",
            "access_token": self.ig_token
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Fetched Instagram media {media_id}: {data.get('media_type')}")
                return data
            except Exception as e:
                logger.error(f"Failed to fetch Instagram media {media_id}: {e}")
                return None

    async def mark_whatsapp_message_read(self, message_id: str):
        """Mark message as read for instant feedback."""
        if not self.wa_token or not self.wa_phone_id or not message_id:
            return
        url = f"https://graph.facebook.com/v18.0/{self.wa_phone_id}/messages"
        headers = {"Authorization": f"Bearer {self.wa_token}", "Content-Type": "application/json"}
        payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, headers=headers, json=payload)
            except Exception as e:
                logger.warning(f"Failed to mark message read: {e}")

    async def send_typing_indicator(self, to_phone: str):
        """Placeholder: WhatsApp Cloud API doesn't support typing indicators."""
        logger.debug(f"Typing indicator requested for {to_phone}")

    async def send_whatsapp_buttons(self, to_phone: str, body_text: str, buttons: list):
        """Send interactive button message (max 3 buttons)."""
        if not self.wa_token or not self.wa_phone_id:
            return {"status": "error", "error": "Missing credentials"}
        
        buttons = buttons[:3]
        headers = {"Authorization": f"Bearer {self.wa_token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}} for b in buttons]}
            }
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.wa_url, headers=headers, json=payload)
                response.raise_for_status()
                return {"status": "sent", "response": response.json()}
            except Exception as e:
                logger.error(f"WhatsApp buttons failed: {e}")
                return {"status": "error", "error": str(e)}


meta_service = MetaService()

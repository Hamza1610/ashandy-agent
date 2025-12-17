"""
Twilio Tools: WhatsApp messaging wrappers using Twilio.
"""
from langchain.tools import tool
from app.services.twilio_service import twilio_service
import logging

logger = logging.getLogger(__name__)


@tool("send_twilio_whatsapp_message")
async def send_twilio_whatsapp_message(user_id: str, message: str) -> str:
    """Send text message via Twilio WhatsApp."""
    try:
        logger.info(f"Sending Twilio WhatsApp to {user_id}")
        result = await twilio_service.send_whatsapp_text(user_id, message)
        return "Message sent" if result and result.get("status") == "sent_via_twilio" else f"Failed: {result}"
    except Exception as e:
        logger.error(f"Twilio WhatsApp error: {e}")
        return f"Error: {str(e)}"


@tool("send_twilio_whatsapp_image")
async def send_twilio_whatsapp_image(user_id: str, image_url: str, caption: str = "") -> str:
    """Send image via Twilio WhatsApp."""
    try:
        logger.info(f"Sending Twilio WhatsApp image to {user_id}")
        result = await twilio_service.send_whatsapp_image(user_id, image_url, caption)
        return "Image sent" if result and result.get("status") == "sent_via_twilio" else f"Failed: {result}"
    except Exception as e:
        logger.error(f"Twilio WhatsApp image error: {e}")
        return f"Error: {str(e)}"

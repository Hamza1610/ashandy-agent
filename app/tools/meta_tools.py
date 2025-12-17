"""
Meta Tools: WhatsApp and Instagram messaging wrappers.
"""
from langchain.tools import tool
from app.services.meta_service import meta_service
import logging

logger = logging.getLogger(__name__)


@tool("send_whatsapp_message_tool")
async def send_whatsapp_message(user_id: str, message: str) -> str:
    """Send text message via WhatsApp."""
    try:
        logger.info(f"Sending WhatsApp to {user_id}")
        result = await meta_service.send_whatsapp_text(user_id, message)
        return "Message sent" if result and result.get("status") == "success" else f"Failed: {result}"
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return f"Error: {str(e)}"


@tool("send_instagram_message_tool")
async def send_instagram_message(user_id: str, message: str) -> str:
    """Send message via Instagram DM."""
    try:
        logger.info(f"Sending Instagram to {user_id}")
        result = await meta_service.send_instagram_text(user_id, message)
        return "Message sent" if result and result.get("status") == "success" else f"Failed: {result}"
    except Exception as e:
        logger.error(f"Instagram error: {e}")
        return f"Error: {str(e)}"


@tool("send_whatsapp_image_tool")
async def send_whatsapp_image(user_id: str, image_url: str, caption: str = "") -> str:
    """Send image via WhatsApp."""
    try:
        logger.info(f"Sending WhatsApp image to {user_id}")
        result = await meta_service.send_whatsapp_image(user_id, image_url, caption)
        return "Image sent" if result and result.get("status") == "success" else f"Failed: {result}"
    except Exception as e:
        logger.error(f"WhatsApp image error: {e}")
        return f"Error: {str(e)}"

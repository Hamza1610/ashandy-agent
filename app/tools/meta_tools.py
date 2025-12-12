"""
Meta platform messaging tools for WhatsApp and Instagram.
"""
from langchain.tools import tool
from app.services.meta_service import meta_service
import logging

logger = logging.getLogger(__name__)


@tool("send_whatsapp_message_tool")
async def send_whatsapp_message(user_id: str, message: str) -> str:
    """
    Send a text message to a user via WhatsApp.
    
    Args:
        user_id: WhatsApp phone number (wa_id)
        message: Text message to send
        
    Returns:
        Send status confirmation
    """
    try:
        logger.info(f"Sending WhatsApp message to {user_id}")
        
        result = await meta_service.send_whatsapp_text(user_id, message)
        
        if result and result.get("status") == "success":
            return f"Message sent successfully via WhatsApp to {user_id}"
        
        return f"Failed to send WhatsApp message: {result}"
        
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return f"Error sending WhatsApp message: {str(e)}"


@tool("send_instagram_message_tool")
async def send_instagram_message(user_id: str, message: str) -> str:
    """
    Send a text message to a user via Instagram DM.
    
    Args:
        user_id: Instagram user ID
        message: Text message to send
        
    Returns:
        Send status confirmation
    """
    try:
        logger.info(f"Sending Instagram message to {user_id}")
        
        result = await meta_service.send_instagram_text(user_id, message)
        
        if result and result.get("status") == "success":
            return f"Message sent successfully via Instagram to {user_id}"
        
        return f"Failed to send Instagram message: {result}"
        
    except Exception as e:
        logger.error(f"Instagram send error: {e}")
        return f"Error sending Instagram message: {str(e)}"


@tool("send_whatsapp_image_tool")
async def send_whatsapp_image(user_id: str, image_url: str, caption: str = "") -> str:
    """
    Send an image via WhatsApp.
    
    Args:
        user_id: WhatsApp phone number
        image_url: URL of the image to send
        caption: Optional caption for the image
        
    Returns:
        Send status confirmation
    """
    try:
        logger.info(f"Sending WhatsApp image to {user_id}")
        
        result = await meta_service.send_whatsapp_image(user_id, image_url, caption)
        
        if result and result.get("status") == "success":
            return f"Image sent successfully via WhatsApp"
        
        return f"Failed to send image: {result}"
        
    except Exception as e:
        logger.error(f"WhatsApp image send error: {e}")
        return f"Error sending image: {str(e)}"

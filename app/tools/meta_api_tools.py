from langchain.tools import tool
from app.services.meta_service import meta_service

@tool
async def send_whatsapp_message(to_phone: str, message: str) -> str:
    """Send a WhatsApp message to a user."""
    response = await meta_service.send_whatsapp_text(to_phone, message)
    if "error" in response:
        return f"Failed to send message: {response['error']}"
    return "Message sent successfully."

@tool
async def send_instagram_message(to_id: str, message: str) -> str:
    """Send an Instagram DM to a user."""
    response = await meta_service.send_instagram_text(to_id, message)
    if "error" in response:
        return f"Failed to send message: {response['error']}"
    return "Message sent successfully."

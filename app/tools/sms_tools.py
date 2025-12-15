"""
SMS Tools: Twilio SMS for rider notifications and manager alerts.
"""
from langchain.tools import tool
from app.utils.config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)


@tool
async def send_rider_sms(rider_phone: str, pickup_location: str, delivery_address: str, order_id: str, customer_phone: str) -> str:
    """Send SMS to rider with delivery details."""
    logger.info(f"Sending rider SMS for order {order_id}")
    
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        logger.error("Twilio credentials missing")
        return "Error: SMS service not configured"
    
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message_body = f"""🚀 DELIVERY #{order_id}
📦 PICKUP: {pickup_location}
📍 DELIVER: {delivery_address}
📞 Customer: {customer_phone}"""
        
        message = client.messages.create(body=message_body, from_=settings.TWILIO_PHONE_NUMBER, to=rider_phone)
        logger.info(f"Rider SMS sent: {message.sid}")
        return f"SMS sent to rider (Order: {order_id})"
        
    except Exception as e:
        logger.error(f"Rider SMS failed: {e}")
        return f"Error: {str(e)}"


@tool
async def notify_manager(order_id: str, customer_name: str, items_summary: str, total_amount: str, delivery_address: str, manager_phone: Optional[str] = None) -> str:
    """Send SMS to manager with order details."""
    logger.info(f"Manager notification for order {order_id}")
    
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        logger.error("Twilio credentials missing")
        return "Error: SMS service not configured"
    
    if not manager_phone and settings.ADMIN_PHONE_NUMBERS:
        manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
    
    if not manager_phone:
        return "Warning: Manager phone not configured"
    
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message_body = f"""💰 ORDER #{order_id}
👤 {customer_name}
🛍️ {items_summary}
💵 {total_amount}
📍 {delivery_address}"""
        
        message = client.messages.create(body=message_body, from_=settings.TWILIO_PHONE_NUMBER, to=manager_phone)
        logger.info(f"Manager SMS sent: {message.sid}")
        return f"Manager notified (Order: {order_id})"
        
    except Exception as e:
        logger.error(f"Manager notification failed: {e}")
        return f"Error: {str(e)}"

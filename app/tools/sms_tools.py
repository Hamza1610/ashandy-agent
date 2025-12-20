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
async def notify_manager(
    order_id: str,
    customer_name: str,
    customer_phone: str,
    items: list,
    subtotal: float,
    delivery_fee: float,
    total_amount: float,
    delivery_address: str,
    delivery_city: str = "",
    email: str = "",
    manager_phone: Optional[str] = None
) -> str:
    """
    Send WhatsApp notification to manager with detailed order and delivery information.
    
    Args:
        order_id: Order reference ID
        customer_name: Customer's full name
        customer_phone: Customer's phone number
        items: List of order items with name, quantity, price
        subtotal: Cart subtotal before delivery
        delivery_fee: Delivery cost
        total_amount: Grand total (subtotal + delivery)
        delivery_address: Full delivery address
        delivery_city: City (optional)
        email: Customer email (optional)
        manager_phone: Manager's phone (uses ADMIN_PHONE_NUMBERS[0] if not provided)
    """
    from app.services.meta_service import meta_service
    from app.utils.config import settings
    
    logger.info(f"Manager notification for order {order_id}")
    
    # Determine manager phone
    if not manager_phone and settings.ADMIN_PHONE_NUMBERS:
        manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
    
    if not manager_phone:
        logger.error("No manager phone configured")
        return "Warning: Manager phone not configured"
    
    try:
        # Format items list
        items_text = ""
        for idx, item in enumerate(items, 1):
            item_name = item.get("name", "Unknown Item")
            item_qty = item.get("quantity", 1)
            item_price = item.get("price", 0)
            items_text += f"{idx}. {item_name} x{item_qty} - ₦{item_price:,.0f}\n"
        
        # Build detailed message
        message_body = f"""🛒 *NEW ORDER NOTIFICATION*

📋 *ORDER DETAILS*
ID: #{order_id}
Items:
{items_text}
Subtotal: ₦{subtotal:,.0f}
Delivery: ₦{delivery_fee:,.0f}
*Total: ₦{total_amount:,.0f}*

📦 *DELIVERY DETAILS*
Full Name: {customer_name}
Phone Number: {customer_phone}
Delivery Address: {delivery_address}
{f"City: {delivery_city}" if delivery_city else ""}
{f"Email: {email}" if email else ""}

✅ Payment confirmed. Ready for processing!"""

        # Send via WhatsApp
        await meta_service.send_whatsapp_text(manager_phone, message_body)
        
        logger.info(f"Manager WhatsApp sent for order {order_id}")
        return f"Manager notified via WhatsApp (Order: {order_id})"
        
    except Exception as e:
        logger.error(f"Manager notification failed: {e}")
        return f"Error: {str(e)}"


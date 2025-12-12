"""
SMS Tools for delivery notifications via Twilio.
Sends SMS to riders for pickup/delivery and to managers for order alerts.
"""
from langchain.tools import tool
from app.utils.config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)


@tool
async def send_rider_sms(
    rider_phone: str,
    pickup_location: str,
    delivery_address: str,
    order_id: str,
    customer_phone: str
) -> str:
    """
    Send SMS to rider with delivery details.
    
    Args:
        rider_phone: Rider's phone number (e.g., "+2348012345678")
        pickup_location: Store/pickup address
        delivery_address: Customer delivery address
        order_id: Order reference ID
        customer_phone: Customer contact number
        
    Returns:
        Status message confirming SMS sent
        
    Example:
        >>> await send_rider_sms(
        ...     "+2348012345678",
        ...     "123 Store St, Lagos",
        ...     "456 Customer Ave, Lagos", 
        ...     "ORD-ABC123",
        ...     "+2348087654321"
        ... )
        "SMS sent to rider successfully"
    """
    print(f"\n>>> TOOL: send_rider_sms called for order {order_id}")
    logger.info(f"Sending rider SMS for order {order_id}")
    
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        logger.error("Twilio credentials missing")
        print(">>> TOOL ERROR: Twilio not configured")
        return "Error: SMS service not configured"
    
    try:
        from twilio.rest import Client
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Compose message for rider
        message_body = f"""🚀 NEW DELIVERY - Order #{order_id}

📦 PICKUP: {pickup_location}

📍 DELIVER TO: {delivery_address}

📞 Customer: {customer_phone}

Please confirm pickup and proceed to delivery location."""
        
        print(f">>> TOOL: Sending SMS to {rider_phone}...")
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=rider_phone
        )
        
        print(f">>> TOOL: SMS sent successfully (SID: {message.sid})")
        logger.info(f"Rider SMS sent: {message.sid}")
        
        return f"SMS sent to rider successfully (Order: {order_id})"
        
    except Exception as e:
        print(f">>> TOOL ERROR: SMS failed - {type(e).__name__}: {str(e)}")
        logger.error(f"Rider SMS failed: {e}", exc_info=True)
        return f"Error sending SMS: {str(e)}"


@tool
async def notify_manager(
    order_id: str,
    customer_name: str,
    items_summary: str,
    total_amount: str,
    delivery_address: str,
    manager_phone: Optional[str] = None
) -> str:
    """
    Send SMS to manager with order details.
    
    Args:
        order_id: Order reference ID
        customer_name: Customer's name
        items_summary: List of ordered items
        total_amount: Total order value
        delivery_address: Delivery location
        manager_phone: Manager's phone (optional, uses default if not provided)
        
    Returns:
        Status message confirming notification sent
        
    Example:
        >>> await notify_manager(
        ...     "ORD-ABC123",
        ...     "Jane Doe",
        ...     "2x Red Lipstick, 1x Foundation",
        ...     "₦12,000",
        ...     "456 Customer Ave, Lagos"
        ... )
        "Manager notified successfully"
    """
    print(f"\n>>> TOOL: notify_manager called for order {order_id}")
    logger.info(f"Sending manager notification for order {order_id}")
    
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        logger.error("Twilio credentials missing")
        print(">>> TOOL ERROR: Twilio not configured")
        return "Error: SMS service not configured"
    
    # Use provided manager phone or first admin number
    if not manager_phone and settings.ADMIN_PHONE_NUMBERS:
        manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
    
    if not manager_phone:
        logger.warning("No manager phone number configured")
        return "Warning: Manager phone not configured, notification skipped"
    
    try:
        from twilio.rest import Client
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Compose message for manager
        message_body = f"""💰 NEW ORDER - #{order_id}

👤 Customer: {customer_name}

🛍️ Items:
{items_summary}

💵 Total: {total_amount}

📍 Delivery: {delivery_address}

Order confirmed and payment received."""
        
        print(f">>> TOOL: Sending manager notification to {manager_phone}...")
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=manager_phone
        )
        
        print(f">>> TOOL: Manager notification sent (SID: {message.sid})")
        logger.info(f"Manager SMS sent: {message.sid}")
        
        return f"Manager notified successfully (Order: {order_id})"
        
    except Exception as e:
        print(f">>> TOOL ERROR: Manager notification failed - {type(e).__name__}: {str(e)}")
        logger.error(f"Manager notification failed: {e}", exc_info=True)
        return f"Error sending notification: {str(e)}"

"""
Delivery Agent: Handles order fulfillment and logistics coordination.

Triggered after payment confirmation to:
1. Send SMS to rider with pickup/delivery details
2. Notify manager of new order
"""
from app.state.agent_state import AgentState
from app.tools.sms_tools import send_rider_sms, notify_manager
from app.utils.config import settings
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def delivery_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Delivery Agent: Coordinates order fulfillment after payment confirmation.
    
    Flow:
        1. Extract order details from state
        2. Send SMS to rider (pickup + delivery info)
        3. Notify manager (order summary)
        4. Update state with delivery status
    
    Args:
        state: Agent state containing order_data with delivery details
        
    Returns:
        Updated state with delivery_status and confirmation messages
    """
    print(f"\n>>> DELIVERY AGENT: Processing order delivery")
    logger.info("Delivery Agent: Starting order fulfillment")
    
    # Get order data from state
    order_data = state.get("order_data", {})
    
    if not order_data:
        logger.warning("No order data found in state")
        print(">>> DELIVERY AGENT WARNING: No order data")
        return {
            "delivery_status": "error",
            "error": "No order data available"
        }
    
    # Extract order details
    order_id = order_data.get("order_id", "UNKNOWN")
    rider_phone = order_data.get("rider_phone")
    pickup_location = order_data.get("pickup_location", "Ashandy Store, Ibadan")
    delivery_address = order_data.get("delivery_address", "Address not provided")
    customer_phone = order_data.get("customer_phone", state.get("user_id", ""))
    customer_name = order_data.get("customer_name", "Customer")
    items_summary = order_data.get("items_summary", "Order items")
    total_amount = order_data.get("total_amount", "₦0")
    manager_phone = order_data.get("manager_phone")
    
    print(f">>> DELIVERY AGENT: Order ID = {order_id}")
    print(f">>> DELIVERY AGENT: Delivery to = {delivery_address}")
    
    rider_status = "pending"
    manager_status = "pending"
    
    # Step 1: Send SMS to rider (if phone provided or use test number)
    rider_phone = order_data.get("rider_phone") or getattr(settings, 'TEST_RIDER_PHONE', None)
    
    if rider_phone:
        print(f">>> DELIVERY AGENT: Sending rider SMS to {rider_phone}")
        rider_result = await send_rider_sms.ainvoke({
            "rider_phone": rider_phone,
            "pickup_location": pickup_location,
            "delivery_address": delivery_address,
            "order_id": order_id,
            "customer_phone": customer_phone
        })
        
        if "successfully" in rider_result.lower():
            rider_status = "sent"
            print(f">>> DELIVERY AGENT: Rider notified ✓")
        else:
            rider_status = "failed"
            print(f">>> DELIVERY AGENT: Rider SMS failed: {rider_result}")
    else:
        rider_status = "skipped"
        print(f">>> DELIVERY AGENT: No rider phone, skipping rider SMS")
    
    # Step 2: Notify manager
    manager_phone_to_use = order_data.get("manager_phone") or getattr(settings, 'TEST_MANAGER_PHONE', None)
    
    print(f">>> DELIVERY AGENT: Notifying manager")
    manager_result = await notify_manager.ainvoke({
        "order_id": order_id,
        "customer_name": customer_name,
        "items_summary": items_summary,
        "total_amount": total_amount,
        "delivery_address": delivery_address,
        "manager_phone": manager_phone_to_use
    })
    
    if "successfully" in manager_result.lower():
        manager_status = "sent"
        print(f">>> DELIVERY AGENT: Manager notified ✓")
    elif "skipped" in manager_result.lower():
        manager_status = "skipped"
        print(f">>> DELIVERY AGENT: Manager notification skipped (no phone)")
    else:
        manager_status = "failed"
        print(f">>> DELIVERY AGENT: Manager notification failed: {manager_result}")
    
    # Prepare completion message
    delivery_summary = f"Order #{order_id} - Delivery notifications processed"
    if rider_status == "sent":
        delivery_summary += "\n✓ Rider notified"
    if manager_status == "sent":
        delivery_summary += "\n✓ Manager notified"
    
    print(f">>> DELIVERY AGENT: Delivery processing complete")
    logger.info(f"Delivery agent completed: rider={rider_status}, manager={manager_status}")
    
    return {
        "delivery_status": "completed",
        "rider_notification_status": rider_status,
        "manager_notification_status": manager_status,
        "delivery_summary": delivery_summary
    }

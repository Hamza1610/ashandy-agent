from app.state.agent_state import AgentState
from app.tools.paystack_tools import generate_payment_link
from app.tools.db_tools import create_order_record
from app.utils.order_parser import (
    extract_order_items,
    calculate_total,
    format_items_summary,
    extract_customer_email
)
from app.utils.config import settings
from langchain_core.messages import SystemMessage, AIMessage
import logging
import uuid
import re

logger = logging.getLogger(__name__)


async def payment_order_agent_node(state: AgentState):
    """
    Payment Agent: Extracts real order details and generates Paystack payment link.
    
    Flow:
        1. Parse conversation for ordered products and prices
        2. Calculate total = items_total + transport_fee
        3. Get customer email (from state or ask)
        4. Generate Paystack link
        5. Prepare order_data for delivery agent
    """
    print(f"\n>>> PAYMENT AGENT: Processing order for user {state.get('user_id')}")
    logger.info(f"Payment Agent: Starting for {state.get('user_id')}")
    
    user_id = state.get("user_id")
    messages = state.get("messages", [])
    
    # Step 1: Extract order items from conversation
    print(f">>> PAYMENT AGENT: Extracting order items from conversation...")
    order_items = extract_order_items(messages)
    
    if not order_items:
        print(f">>> PAYMENT AGENT WARNING: No items found in conversation")
        logger.warning("No order items extracted from conversation")
        
        # Fallback: Try to extract from request_payment_link tool call
        for msg in reversed(messages):
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                    if 'payment_link' in tool_name.lower():
                        args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                        product_names = args.get('product_names', 'Unknown Product')
                        total_from_tool = float(args.get('total_amount', 0))
                        
                        if total_from_tool > 0:
                            order_items = [{
                                "name": product_names,
                                "price": total_from_tool,
                                "quantity": 1
                            }]
                            print(f">>> PAYMENT AGENT: Using fallback from tool call: {product_names} @ ₦{total_from_tool:,.0f}")
                        break
    
    if not order_items:
        # Ultimate fallback
        order_items = [{
            "name": "Beauty Products",
            "price": 5000.0,
            "quantity": 1
        }]
        print(f">>> PAYMENT AGENT: Using default fallback order")
    
    # Step 2: Calculate totals
    transport_fee = getattr(settings, 'TRANSPORT_FEE', 500.0)
    totals = calculate_total(order_items, transport_fee)
    
    items_total = totals["items_total"]
    total_amount = totals["total"]
    
    print(f">>> PAYMENT AGENT: Order Summary:")
    print(f">>>   Items Total: ₦{items_total:,.2f}")
    print(f">>>   Transport: ₦{transport_fee:,.2f}")
    print(f">>>   TOTAL: ₦{total_amount:,.2f}")
    
    # Step 3: Get customer email
    customer_email = extract_customer_email(messages, state)
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not customer_email or not re.match(email_pattern, customer_email):
        # Invalid or missing email - ask user to provide valid one
        print(f">>> PAYMENT AGENT: Invalid/missing email - asking customer")
        logger.warning(f"Invalid email for {user_id}: {customer_email}")
        
        return {
            "messages": [AIMessage(
                content="I need a valid email address to process your payment. "
                       "Please provide your email (e.g., yourname@example.com)."
            )]
        }
    
    print(f">>> PAYMENT AGENT: Valid email confirmed: {customer_email}")
    
    # Step 4: Generate unique reference
    reference = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    print(f">>> PAYMENT AGENT: Generating Paystack link...")
    print(f">>>   Reference: {reference}")
    
    # Store Order Details for later retrieval (Webhook)
    order_data = state.get("order_data", {})
    delivery_details = state.get("delivery_details", {})
    delivery_fee = state.get("delivery_fee", 0)
    
    full_details = {
        "items": order_data.get("items", []),
        "subtotal": order_data.get("subtotal", amount),
        "delivery_fee": delivery_fee,
        "delivery_details": delivery_details,
        "delivery_type": state.get("delivery_type", "Pickup")
    }
    
    await create_order_record(
        user_id=user_id,
        amount=amount + delivery_fee,
        reference=reference,
        details=full_details
    )
    
    try:
        # Generate actual Paystack link
        from app.tools.payment_tools import generate_payment_link
        link_result = await generate_payment_link.ainvoke({
            "email": customer_email,
            "amount": total_amount,
            "reference": reference
        })
        
        print(f">>> PAYMENT AGENT: ✓ Payment link generated successfully!")
        logger.info(f"Payment link created: {reference} for ₦{total_amount:,.2f}")
        
        # Step 5: Prepare order_data for delivery agent
        items_summary = format_items_summary(order_items)
        
        order_data = {
            "order_id": reference,
            "user_id": user_id,
            "customer_email": customer_email,
            "customer_name": state.get("user_name", "Customer"),
            "customer_phone": user_id,  # WhatsApp/Instagram ID is phone-based
            "items": order_items,
            "items_summary": items_summary,
            "items_total": items_total,
            "transport_fee": transport_fee,
            "total_amount": f"₦{total_amount:,.0f}",
            "paystack_reference": reference,
            "payment_link": link_result,
            # Delivery info (to be added by user or config)
            "pickup_location": "Ashandy Store, Ibadan",
            "delivery_address": state.get("delivery_address", "To be confirmed"),
            "rider_phone": state.get("rider_phone"),  # Optional
            "manager_phone": None  # Will use ADMIN_PHONE_NUMBERS
        }
        
        print(f">>> PAYMENT AGENT: Order data prepared for delivery")
        
        return {
            "order_intent": True,
            "order_data": order_data,
            "paystack_reference": reference,
            "messages": [AIMessage(content=link_result)]
        }
        
    except Exception as e:
        print(f">>> PAYMENT AGENT ERROR: {type(e).__name__}: {str(e)}")
        logger.error(f"Payment link generation failed: {e}", exc_info=True)
        
        return {
            "error": str(e),
            "messages": [AIMessage(
                content="Sorry, I encountered an issue generating your payment link. "
                       "Please try again or contact our support team for assistance."
            )]
        }

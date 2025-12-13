from app.state.agent_state import AgentState
from app.tools.payment_tools import generate_payment_link
from app.utils.order_parser import (
    extract_order_items,
    calculate_total,
    format_items_summary,
    extract_customer_email
)
from app.utils.config import settings
from app.services.order_service import create_order
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
    
    # Step 3: Get customer email from STATE (set by webhook from contacts)
    customer_email = state.get("customer_email")
    
    print(f">>> PAYMENT AGENT: Customer email from state: {customer_email}")
    
    # If no email in state, try to extract from messages (fallback)
    if not customer_email:
        print(f">>> PAYMENT AGENT: No email in state, trying to extract from messages...")
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
        
        # Step 6: Save order to database
        try:
            print(f">>> PAYMENT AGENT: Saving order to database...")
            db_order = await create_order(
                user_id=user_id,
                paystack_reference=reference,
                customer_email=customer_email,
                customer_name=state.get("user_name", "Customer"),
                customer_phone=user_id,
                items=order_items,
                items_total=items_total,
                transport_fee=transport_fee,
                total_amount=total_amount,
                payment_link=link_result,
                delivery_address=state.get("delivery_address", "To be confirmed"),
                pickup_location="Ashandy Store, Ibadan"
            )
            print(f">>> PAYMENT AGENT: ✓ Order saved to database (ID: {db_order.order_id})")
            logger.info(f"Order saved: {db_order.order_id}")
            
            # Add order ID to order_data
            order_data["db_order_id"] = str(db_order.order_id)
            
        except Exception as e:
            # Log error but continue - don't block payment link from being sent
            print(f">>> PAYMENT AGENT WARNING: Failed to save order to DB: {e}")
            logger.error(f"Order save failed: {e}", exc_info=True)
        
        # Create user-friendly message
        items_summary = format_items_summary(order_items)
        payment_message = f"""✅ *Payment Link Ready!*

*Order Summary:*
{items_summary}

*Pricing:*
• Items: ₦{items_total:,.0f}
• Delivery: ₦{transport_fee:,.0f}
• *Total: ₦{total_amount:,.0f}*

*Complete your payment here:*
{link_result}

Once paid, we'll confirm your order and arrange delivery! 📦"""
        
        return {
            "order_intent": True,
            "order_data": order_data,
            "paystack_reference": reference,
            "customer_email": customer_email,  # Persist email in state
            "messages": [AIMessage(content=payment_message)]
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

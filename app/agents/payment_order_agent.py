from app.models.agent_states import AgentState
from app.tools.paystack_tools import generate_payment_link
from app.tools.db_tools import create_order_record
from langchain_core.messages import SystemMessage
import logging
import uuid # For reference generation

logger = logging.getLogger(__name__)

async def payment_order_agent_node(state: AgentState):
    """
    Payment Agent: Handles order creation and payment link generation.
    """
    user_id = state.get("user_id")
    # In a real flow, we would extract order details (amount, items) from the conversation state
    # populated by the Sales Agent (using structured output).
    # For this MVP, we will assume a fixed amount or extract simplisticly.
    
    # Mocking order extraction source
    amount = 5000.00 # Default fallback
    email = "customer@example.com" # Should be fetched from user profile
    
    reference = str(uuid.uuid4())
    
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
        # 1. Generate Link
        link_result = await generate_payment_link.ainvoke({
            "email": email,
            "amount": amount + delivery_fee, # Total
            "reference": reference
        })
        
        if "Failed" in link_result:
            return {"error": "Payment link generation failed."}
            
        return {
            "paystack_reference": reference,
            "messages": [SystemMessage(content=f"Here is your payment link: {link_result}")]
        }
        
    except Exception as e:
        logger.error(f"Payment Agent Error: {e}")
        return {"error": str(e)}

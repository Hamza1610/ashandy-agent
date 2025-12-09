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
    
    try:
        # 1. Generate Link
        link_result = await generate_payment_link.ainvoke({
            "email": email,
            "amount": amount,
            "reference": reference
        })
        
        if "Failed" in link_result:
            return {"error": "Payment link generation failed."}
            
        # 2. Create Order Record
        # await create_order_record.ainvoke(user_id, amount, reference)
        
        return {
            "paystack_reference": reference,
            "messages": [SystemMessage(content=f"Here is your payment link: {link_result}")]
        }
        
    except Exception as e:
        logger.error(f"Payment Agent Error: {e}")
        return {"error": str(e)}

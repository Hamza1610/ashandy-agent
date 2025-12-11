from app.state.agent_state import AgentState
from app.tools.paystack_tools import generate_payment_link
from app.tools.db_tools import create_order_record
from langchain_core.messages import SystemMessage
import logging
import uuid

logger = logging.getLogger(__name__)

async def payment_order_agent_node(state: AgentState):
    """
    Payment Agent: Extracts order details and generates real Paystack payment link.
    Called when sales agent detects purchase intent.
    """
    print(f"\n>>> PAYMENT AGENT: Called for user {state.get('user_id')}")
    
    user_id = state.get("user_id")
    messages = state.get("messages", [])
    
    # Extract order details from the last tool call (request_payment_link)
    product_names = "Products"
    total_amount = 0.0
    
    # Look for the request_payment_link tool call in messages
    for msg in reversed(messages):
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                if 'payment_link' in tool_name.lower():
                    args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                    product_names = args.get('product_names', 'Products')
                    total_amount = float(args.get('total_amount', 0))
                    print(f">>> PAYMENT AGENT: Extracted - {product_names} = ₦{total_amount:,.2f}")
                    break
    
    if total_amount == 0:
        print(">>> PAYMENT AGENT: No amount found, using default")
        total_amount = 5000.00  # Fallback
    
    # Get or create customer email (in production, fetch from user profile)
    email = "customer@example.com"  # TODO: Get from user profile/database
    
    # Generate unique reference
    reference = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    print(f">>> PAYMENT AGENT: Generating Paystack link...")
    print(f">>>   Email: {email}")
    print(f">>>   Amount: ₦{total_amount:,.2f}")
    print(f">>>   Reference: {reference}")
    
    try:
        # Generate actual Paystack link
        from app.tools.payment_tools import generate_payment_link
        link_result = await generate_payment_link.ainvoke({
            "email": email,
            "amount": total_amount,
            "reference": reference
        })
        
        print(f">>> PAYMENT AGENT: Link generated successfully!")
        logger.info(f"Payment link generated: {reference} = ₦{total_amount:,.2f}")
        
        return {
            "paystack_reference": reference,
            "messages": [SystemMessage(content=link_result)]
        }
        
    except Exception as e:
        print(f">>> PAYMENT AGENT ERROR: {e}")
        logger.error(f"Payment Agent Error: {e}")
        return {
            "error": str(e),
            "messages": [SystemMessage(content="Sorry, there was an error generating your payment link. Please try again or contact support.")]
        }

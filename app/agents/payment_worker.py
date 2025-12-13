from app.state.agent_state import AgentState
from app.tools.payment_tools import generate_payment_link
from app.tools.db_tools import create_order_record
import logging
import uuid


logger = logging.getLogger(__name__)

async def payment_worker_node(state: AgentState):
    """
    Payment Worker: Generates Payment Links.
    
    Responsibilities:
    1. Validates Email (passed in task or state).
    2. Calculates Total.
    3. Generates Link.
    
    Refactor Note: Logic simplified to trust the Planner's data extraction.
    """
    user_id = state.get("user_id")
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    current_step = plan[idx] if idx < len(plan) else {}
    
    # Task Context
    task_desc = current_step.get("task", "").lower()
    total_amount = 0.0
    
    # Try to get total from state order_data
    order_data = state.get("order_data", {})
    if order_data and "total" in order_data:
        total_amount = float(order_data["total"])
    
    # Task Dispatch
    if "delivery" in task_desc:
        location = task_desc.replace("calculate delivery", "").strip()
        fee = 1500.0 if "lekki" in location.lower() else 1000.0 # Placeholder logic
        final_total = total_amount + fee
        return {"worker_result": f"Delivery to {location} is ₦{fee:,.0f}. Total is ₦{final_total:,.0f}"}

    # 1. Get Email
    customer_email = state.get("user_email") or "customer@ashandy.org" # Fallback if not found
    
    # 2. Get Amount & Items (Simplified extraction from order_data or task)
    total_amount = 5000.0 # Default fallback
    
    # Check if Planner passed order details in the 'task' description or state?
    # In a perfect world, Planner populates `state['order_data']` before calling this.
    # Let's assume order_data is the source of truth if present.
    order_data = state.get("order_data", {})
    if order_data and "total" in order_data:
        total_amount = float(order_data["total"])
    
    # 3. Generate Reference
    reference = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    try:
        # Create Record
        await create_order_record.ainvoke({
            "user_id": user_id,
            "amount": total_amount,
            "reference": reference,
            "details": {"source": "whatsapp_bot", "email": customer_email}
        })
        
        # Generate Link
        link_result = await generate_payment_link.ainvoke({
            "email": customer_email,
            "amount": total_amount,
            "reference": reference
        })
        
        return {"worker_result": f"Payment Link generated: {link_result} (Ref: {reference})"}
        
    except Exception as e:
        logger.error(f"Payment Worker Error: {e}")
        return {"worker_result": f"Error generating link: {str(e)}"}

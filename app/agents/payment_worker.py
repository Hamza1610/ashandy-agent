from app.state.agent_state import AgentState
from app.tools.payment_tools import generate_payment_link
from app.tools.db_tools import create_order_record
from app.tools.tomtom_tools import calculate_delivery_fee
from app.tools.delivery_validation_tools import (
    request_delivery_details, 
    check_delivery_ready,
    DEFAULT_EMAIL
)
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, AIMessage
from app.utils.config import settings
import logging
import json

logger = logging.getLogger(__name__)

async def payment_worker_node(state: AgentState):
    """
    Payment Worker: Generates Payment Links & Calculates Delivery.
    
    Architecture:
    - Model: Llama 3.1 8B Instant (Fast & Cheap)
    - Pattern: ReAct / Tool Calling
    - Validation: Delivery details MUST be provided before payment link
    """
    try:
        # 1. Pub/Sub Task Retrieval
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses", {})
        
        # Find the task assigned to ME that is IN_PROGRESS
        my_task = None
        for step in plan:
            if step.get("worker") == "payment_worker" and task_statuses.get(step["id"]) == "in_progress":
                my_task = step
                break
        
        if not my_task:
            return {"worker_result": "No active task found for payment_worker."}
            
        task_desc = my_task.get("task", "")
        logger.info(f"💳 PAYMENT WORKER: Executing '{task_desc}'")

        # 2. Context Extraction (Reviewer Feedback Loop)
        retry_count = state.get("retry_counts", {}).get(my_task["id"], 0)
        critique = state.get("reviewer_critique", "")
        
        context_str = ""
        if retry_count > 0 and critique:
            context_str = f"⚠️ PREVIOUS ATTEMPT REJECTED. Fix this: {critique}"

        # 3. Extract order and delivery data from state
        order_data = state.get("order_data", {})
        delivery_details = order_data.get("delivery_details", {})
        customer_email = state.get("customer_email") or delivery_details.get("email") or DEFAULT_EMAIL
        
        # 4. Check if this is a payment link task - validate delivery details first
        is_payment_task = "payment" in task_desc.lower() or "link" in task_desc.lower()
        delivery_ready_msg = ""
        
        if is_payment_task and order_data.get("delivery_type", "").lower() != "pickup":
            # Check delivery details
            check_result = await check_delivery_ready.ainvoke({"order_data": order_data})
            
            if not check_result.get("ready", False):
                missing = check_result.get("missing", [])
                logger.warning(f"Payment Worker: Missing delivery details: {missing}")
                
                # Request delivery details from customer
                request_msg = await request_delivery_details.ainvoke({})
                return {
                    "worker_outputs": {my_task["id"]: f"❌ Cannot process payment yet.\n\n{request_msg}\n\nMissing: {', '.join(missing)}"},
                    "worker_tool_outputs": {my_task["id"]: []},
                    "messages": [AIMessage(content=f"❌ Cannot process payment yet.\n\n{request_msg}\n\nMissing: {', '.join(missing)}")]
                }
            else:
                customer_email = check_result.get("email", DEFAULT_EMAIL)
                delivery_ready_msg = "✅ Delivery details validated."

        # 5. Setup Tools & Model
        tools = [calculate_delivery_fee, generate_payment_link, create_order_record]
        
        llm = ChatGroq(
            temperature=0.0,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="llama-3.1-8b-instant"
        ).bind_tools(tools)
        
        # 6. Prompt Engineering (Robust System Prompt)
        system_prompt = f"""You are the **Payment & Logistics Manager** for Ashandy Cosmetics.

**Your Goal:** Execute the assigned task precisely using the available tools.

**Tools:**
1. `calculate_delivery_fee(location)`: Use exactly the location provided.
2. `create_order_record(user_id, amount, reference, details)`: Call this BEFORE generating a link.
3. `generate_payment_link(amount, reference, email, delivery_details)`: Call this LAST.

**Current Task:** "{task_desc}"
{context_str}
{delivery_ready_msg}

**Context:**
User ID: {state.get('user_id')}
User Email: {customer_email}
Order Data: {json.dumps(order_data, default=str)}
Delivery Details: {json.dumps(delivery_details, default=str)}

**CRITICAL RULES:**
- If checking delivery, just return the fee.
- If generating payment link:
  1. FIRST create the order record
  2. THEN generate the payment link with delivery_details included
  3. Use email '{customer_email}' (fallback: {DEFAULT_EMAIL})
- Return a clear, human-readable confirmation string.
"""

        messages = [SystemMessage(content=system_prompt)]
        
        # 7. Execution Loop (Simple Tool Call)
        response = await llm.ainvoke(messages)
        final_output = response.content or ""
        tool_evidence = []

        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Payment Worker calling {name} with {args}")
                
                # Inject delivery_details into payment link call if not provided
                if name == "generate_payment_link":
                    if "delivery_details" not in args:
                        args["delivery_details"] = delivery_details
                    if "email" not in args or not args.get("email"):
                        args["email"] = customer_email
                
                # Manual Tool Execution Map
                tool_res = ""
                if name == "calculate_delivery_fee":
                    tool_res = await calculate_delivery_fee.ainvoke(args)
                elif name == "generate_payment_link":
                    tool_res = await generate_payment_link.ainvoke(args)
                elif name == "create_order_record":
                    tool_res = await create_order_record.ainvoke(args)
                
                # CAPTURE EVIDENCE
                tool_evidence.append({
                    "tool": name,
                    "args": args,
                    "output": str(tool_res)[:500]
                })

                # Append result to output
                final_output += f"\nResult of {name}: {str(tool_res)}"
                
        # 8. Return Result
        return {
            "worker_outputs": {my_task["id"]: final_output},
            "worker_tool_outputs": {my_task["id"]: tool_evidence},
            "messages": [AIMessage(content=final_output)]
        }

    except Exception as e:
        logger.error(f"Payment Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error: {str(e)}"}


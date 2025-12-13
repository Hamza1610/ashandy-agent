from app.state.agent_state import AgentState
from app.tools.payment_tools import generate_payment_link
from app.tools.db_tools import create_order_record
from app.tools.tomtom_tools import calculate_delivery_fee
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

        # 3. Setup Tools & Model
        tools = [calculate_delivery_fee, generate_payment_link, create_order_record]
        
        llm = ChatGroq(
            temperature=0.0,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="llama-3.1-8b-instant"
        ).bind_tools(tools)
        
        # 4. Prompt Engineering (Robust System Prompt)
        system_prompt = f"""You are the **Payment & Logistics Manager** for Ashandy Cosmetics.

**Your Goal:** Execute the assigned task precisely using the available tools.

**Tools:**
1. `calculate_delivery_fee(location)`: Use exactly the location provided.
2. `create_order_record(user_id, amount, reference, details)`: Call this BEFORE generating a link.
3. `generate_payment_link(email, amount, reference)`: Call this LAST.

**Current Task:** "{task_desc}"
{context_str}

**Context:**
User ID: {state.get('user_id')}
User Email: {state.get('customer_email', 'unknown')}
Order Data: {state.get('order_data', {})}

**Rules:**
- If checking delivery, just return the fee.
- If generating link, YOU MUST create the order record first. 
- Return a clear, human-readable confirmation string as your final answer.
"""

        messages = [SystemMessage(content=system_prompt)]
        
        # 5. Execution Loop (Simple Tool Call)
        response = await llm.ainvoke(messages)
        final_output = response.content or ""
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Payment Worker calling {name} with {args}")
                
                # Manual Tool Execution Map
                tool_res = ""
                if name == "calculate_delivery_fee":
                    tool_res = await calculate_delivery_fee.ainvoke(args)
                elif name == "generate_payment_link":
                    tool_res = await generate_payment_link.ainvoke(args)
                elif name == "create_order_record":
                    tool_res = await create_order_record.ainvoke(args)
                
                # Append result to output
                final_output += f"\nResult of {name}: {str(tool_res)}"
                
        # 6. Return Result
        return {
            "worker_outputs": {my_task["id"]: final_output},
            "messages": [AIMessage(content=final_output)]
        }

    except Exception as e:
        logger.error(f"Payment Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error: {str(e)}"}

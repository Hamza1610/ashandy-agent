from app.state.agent_state import AgentState
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage

from app.utils.config import settings
import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def planner_agent_node(state: AgentState):
    """
    Planner Agent: The Brain.
    
    Responsibilities:
    1. Analyze user intent.
    2. Check Business Rules (Inventory > 25k, Sentiment).
    3. Break down complex requests into a sequential PLAN.
    4. For simple requests, assign a single 'Direct Reply' task (Fast-Path).
    
    Outputs:
    - plan: List[TaskStep]
    - current_step_index: 0
    """
    if not settings.LLAMA_API_KEY:
        return {"error": "LLM API Key missing."}

    messages = state.get("messages", [])
    if not messages:
        return {"error": "No messages"}

    # Get context (previous plan results if loop, visual context, etc)
    user_id = state.get("user_id")
    visual_context = state.get("visual_matches", "")
    
    # SYSTEM PROMPT FOR PLANNING
    system_prompt = """You are the **Main Planner** for Ashandy Cosmetics AI 'Awelewa'.
    
**Your Job:**
Analyze the user's message and create a step-by-step Execution Plan.

**Available Workers:**
1. `sales_worker`: Handles product search, explanation, visual analysis, and general chat.
2. `admin_worker`: Handles '/commands' (sync, report, stock), stock queries, and incident reporting.
3. `payment_worker`: Generates payment links and collects emails.

**Business Rules (CRITICAL):**
1. **Approval Rule:** If user wants to buy items with Total Value > ₦25,000 -> Assign `request_approval` task to `admin_worker`.
2. **Visual Rule:** If message has an image -> Assign `analyze_image` task to `sales_worker` FIRST.
3. **Delivery Rule:** If user is buying -> Assign `calculate_delivery` task to `payment_worker` BEFORE `generate_link`.
4. **Context Rule:** If user references past events ("Remember what I said") -> Assign `retrieve_memory` task to `sales_worker`.
5. **Sentiment Rule:** If user is HOSTILE, uses profanity, or calls 'scam' -> Assign `handover` task to `admin_worker` (URGENT).
6. **Handoff Policy:** 
   - If user asks for "Manager" or "Human" normally: DO NOT handoff. Assign `sales_worker` task: "Ask why they need a manager and offer to help first".
   - Only handoff if user is insistent, angry, or claims an emergency.

**ADMIN / MANAGER MODE:**
If `is_admin` is True, you are the **Chief of Staff**.
- If Manager says "Approve" (or similar): Assign `approve_order` task to `admin_worker`.
- If Manager says "Reject", "No", or gives a reason ("Out of stock"): Assign `reject_order` task to `admin_worker` with the reason.
- If Manager asks "Who is pending?": Assign `list_pending_approvals` task to `admin_worker`.
- If Manager's intent is ambiguous ("Yes"), still assign `approve_order` (the tool handles ambiguity).

**Output Format (JSON ONLY):**
Return a JSON object with a 'plan' list.
Each item in 'plan': {"id": "step1", "worker": "sales_worker", "task": "Search for 'Ringlight'", "reason": "User asked for price"}

**Fast-Path Examples:**
- User: "Hi" -> Plan: `[{"worker": "sales_worker", "task": "Greet user warmly", "reason": "Greeting"}]`
- User: [Image] -> Plan: `[{"worker": "sales_worker", "task": "Analyze image and find products", "reason": "Visual Search"}]`
- Admin: "Approve" -> Plan: `[{"worker": "admin_worker", "task": "Execute command: /approve", "reason": "Manager Command"}]`

**Complex Example:**
- User: "I want 5 ringlights (10k each) delivered to Lekki"
- Plan: 
  1. `{"worker": "sales_worker", "task": "Confirm stock for 5 ringlights", "reason": "Check availability"}`
  2. `{"worker": "payment_worker", "task": "Calculate delivery fee for Lekki", "reason": "Delivery calc"}`
  3. `{"worker": "admin_worker", "task": "Request approval for 50k order", "reason": "High Value"}`

**Current Context:**
"""
    if visual_context:
        system_prompt += f"\n(Visual Info: {visual_context})\n"

    # We need to construct the LLM call
    llm = ChatGroq(
        temperature=0.0, # Strict logic
        groq_api_key=settings.LLAMA_API_KEY,
        model_name="meta-llama/llama-4-scout-17b-16e-instruct", # Using a smarter model for Planning
        response_format={"type": "json_object"}
    )
    
    conversation = [SystemMessage(content=system_prompt)]
    recent_messages = messages[-5:] if len(messages) > 5 else messages
    conversation.extend(recent_messages)
    
    try:
        response = await llm.ainvoke(conversation)
        content = response.content
        logger.info(f"Planner raw output: {content}")
        
        # Parse JSON
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found")
            
        json_str = content[start:end]
        plan_data = json.loads(json_str)
        plan_list = plan_data.get("plan", [])
        
        if not plan_list:
            # Fallback for empty plan
            plan_list = [{"worker": "sales_worker", "task": "Reply to user", "reason": "Fallback"}]
            
        logger.info(f"Planner generated {len(plan_list)} steps.")
        
        return {
            "plan": plan_list,
            "current_step_index": 0,
            "planner_thought": f"Created plan with {len(plan_list)} steps."
        }

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        # Fallback plan
        fallback_plan = [{"worker": "sales_worker", "task": "Reply to user politely", "reason": "Planner Error"}]
        return {"plan": fallback_plan, "current_step_index": 0}

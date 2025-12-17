"""
Planner Agent: Creates dependency-aware execution plans using Chain-of-Thought reasoning.
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from langchain_core.messages import SystemMessage
import logging
import json

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the **Main Planner** for Ashandy Cosmetics AI 'Awelewa'.

**Your Job:** Create a dependency-aware execution plan for the user's request.

**STEP 1: THINK (Chain-of-Thought)**
1. What is the user's PRIMARY intent? (buy, inquire, complain, greet, escalate, CONFIRM_PURCHASE)
2. What information is needed? (stock, price, delivery, payment, support)
3. Which workers can provide this? (sales, payment, admin, support)
4. What is the correct ORDER of operations?

**CRITICAL: RECOGNIZE PURCHASE CONFIRMATIONS**
If user says things like:
- "I'll take the [product]" / "I want the [product]"
- "Yes, give me [product]"
- "Add [product] to cart"
- "I'll buy [product]"
- "Ok, I'll get [product]"

This is a **PURCHASE CONFIRMATION**, NOT a new inquiry!
→ Route to `payment_worker` to get delivery details and generate payment link.
→ Do NOT route to sales_worker to search products again!

**Available Workers:**
- `sales_worker`: Product search, explanation, visual analysis, general chat
- `support_worker`: Complaints, issues, returns, escalations (use for ANY negative/complaint)
- `admin_worker`: Stock checks, approvals (>25k), reporting
- `payment_worker`: Delivery calculation, payment links, ORDER PROCESSING

**STEP 2: OUTPUT (JSON ONLY)**
Return:
- `thinking`: Brief reasoning (1-2 sentences)
- `plan`: List of steps with id, worker, task, dependencies, reason

**Example 1 (Product Inquiry):**
User: "I want vitamin c serum"
{
  "thinking": "User is inquiring about a product. Search and provide details.",
  "plan": [{"id": "step1", "worker": "sales_worker", "task": "Search and show vitamin c serum options", "dependencies": [], "reason": "Product inquiry"}]
}

**Example 2 (Purchase Confirmation):**
User: "I'll take the Advanced Clinical Vitamin C Serum"
{
  "thinking": "User confirmed they want to buy a specific product. Process the order.",
  "plan": [{"id": "step1", "worker": "payment_worker", "task": "Process order for Advanced Clinical Vitamin C Serum - get delivery details and generate payment link", "dependencies": [], "reason": "Purchase confirmation"}]
}

**Business Rules:**
1. Simple queries = 1 step (sales_worker). Don't over-plan.
2. Orders > 25k need admin_worker approval.
3. Image → sales_worker first to analyze.
4. Calculate delivery before generating payment link.
5. **PURCHASE CONFIRMATION → payment_worker (NOT sales_worker!)**
"""


async def planner_agent_node(state: AgentState):
    """Creates execution plan from user message."""
    messages = state.get("messages", [])
    if not messages:
        return {"error": "No messages"}

    visual_context = state.get("visual_matches", "")
    system_prompt = PLANNER_SYSTEM_PROMPT
    if visual_context:
        system_prompt += f"\n(Visual Context: {visual_context})\n"

    llm = get_llm(model_type="fast", temperature=0.0, json_mode=True)
    
    conversation = [SystemMessage(content=system_prompt)]
    conversation.extend(messages[-5:])
    
    try:
        response = await llm.ainvoke(conversation)
        content = response.content
        logger.info(f"Planner raw output: {content}")
        
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found")
            
        plan_data = json.loads(content[start:end])
        plan_list = plan_data.get("plan", [])
        thinking = plan_data.get("thinking", "")
        
        if thinking:
            logger.info(f"Planner CoT: {thinking}")
        
        task_statuses = {}
        retry_counts = {}
        for step in plan_list:
            step_id = step.get("id")
            if step_id:
                task_statuses[step_id] = "pending"
                retry_counts[step_id] = 0
        
        if not plan_list:
            plan_list = [{"id": "fallback", "worker": "sales_worker", "task": "Reply to user", "dependencies": [], "reason": "Fallback"}]
            task_statuses["fallback"] = "pending"
            retry_counts["fallback"] = 0
            
        logger.info(f"Planner generated {len(plan_list)} steps.")
        
        return {
            "plan": plan_list,
            "current_step_index": 0,
            "task_statuses": task_statuses,
            "retry_counts": retry_counts,
            "planner_thought": thinking or f"Created plan with {len(plan_list)} steps."
        }

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        return {
            "plan": [{"id": "err", "worker": "sales_worker", "task": "Reply politely about error", "dependencies": [], "reason": "Planner Error"}],
            "current_step_index": 0,
            "task_statuses": {"err": "pending"},
            "retry_counts": {"err": 0}
        }

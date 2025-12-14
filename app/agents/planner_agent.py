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
1. What is the user's PRIMARY intent? (buy, inquire, complain, greet)
2. What information is needed? (stock, price, delivery, payment)
3. Which workers can provide this? (sales, payment, admin)
4. What is the correct ORDER of operations?

**Available Workers:**
- `sales_worker`: Product search, explanation, visual analysis, chat
- `admin_worker`: Stock checks, approvals (>25k), reporting
- `payment_worker`: Delivery calculation, payment links

**STEP 2: OUTPUT (JSON ONLY)**
Return:
- `thinking`: Brief reasoning (1-2 sentences)
- `plan`: List of steps with id, worker, task, dependencies, reason

**Example:**
User: "I want 5 ringlights (10k each) delivered to Lekki"
{
  "thinking": "User wants ringlights with delivery. Check stock, calculate delivery, get approval.",
  "plan": [
    {"id": "step1", "worker": "sales_worker", "task": "Confirm stock for 5 ringlights", "dependencies": [], "reason": "Check availability"},
    {"id": "step2", "worker": "payment_worker", "task": "Calculate delivery to Lekki", "dependencies": [], "reason": "Parallel task"},
    {"id": "step3", "worker": "admin_worker", "task": "Request approval for 50k", "dependencies": ["step1", "step2"], "reason": "After confirmation"}
  ]
}

**Business Rules:**
1. Simple queries = 1 step (sales_worker). Don't over-plan.
2. Orders > 25k need admin_worker approval.
3. Image → sales_worker first to analyze.
4. Calculate delivery before generating payment link.
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

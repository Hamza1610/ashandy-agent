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
Analyze the user's message and create a **Dependency-Aware Execution Plan**.
We use a **Pub/Sub Architecture**: You publish tasks, and Workers pick them up based on dependencies.

**Available Workers:**
1. `sales_worker`: Product search, explanation, visual analysis, chat.
2. `admin_worker`: Commands, stock checks, approvals (>25k), reporting.
3. `payment_worker`: Delivery calculation, payment links.

**Output Format (JSON ONLY):**
Return a JSON object with a 'plan' list.
Each item must have:
- `id`: "step1", "step2", etc.
- `worker`: "sales_worker", "admin_worker", or "payment_worker"
- `task`: Detailed instruction.
- `dependencies`: List of IDs that must finish BEFORE this step. [] for no dependencies.
- `reason`: Why this step is needed.

**Example:**
User: "I want 5 ringlights (10k each) delivered to Lekki"
Plan:
[
  {
    "id": "step1", 
    "worker": "sales_worker", 
    "task": "Confirm stock for 5 ringlights", 
    "dependencies": [], 
    "reason": "Check availability"
  },
  {
    "id": "step2", 
    "worker": "payment_worker", 
    "task": "Calculate delivery fee for Lekki", 
    "dependencies": [], 
    "reason": "Can run parallel to stock check"
  },
  {
    "id": "step3", 
    "worker": "admin_worker", 
    "task": "Request approval for 50k order", 
    "dependencies": ["step1", "step2"], 
    "reason": "Needs stock and delivery confirmed first"
  }
]

**Business Rules:**
1. **Approval:** Orders > 25k need `admin_worker` approval.
2. **Visual:** Image -> `sales_worker` first.
3. **Delivery:** Always calculate delivery before payment.

**Current Context:**
"""
    if visual_context:
        system_prompt += f"\n(Visual Info: {visual_context})\n"

    # Hybrid Stack: Planner uses Scout 17B (Reverted per user request)
    llm = ChatGroq(
        temperature=0.0,
        groq_api_key=settings.LLAMA_API_KEY,
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
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
        
        # Initialize Task Statuses
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
            "planner_thought": f"Created plan with {len(plan_list)} steps."
        }

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        fallback_plan = [{"id": "err", "worker": "sales_worker", "task": "Reply politely about error", "dependencies": [], "reason": "Planner Error"}]
        return {
            "plan": fallback_plan, 
            "current_step_index": 0,
            "task_statuses": {"err": "pending"},
            "retry_counts": {"err": 0}
        }

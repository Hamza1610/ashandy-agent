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

**CRITICAL: PURCHASE FLOW (Multi-Stage)**

**STAGE 1: ADD TO ORDER** (route to sales_worker, NOT payment_worker!)
If user says things like:
- "I'll take the [product]" / "I want the [product]"
- "Yes, give me [product]"
- "Add [product] to cart" / "I'll buy [product]"
- "Ok, I'll get [product]"

This is ADDING to their order, NOT checkout!
→ Route to `sales_worker` with task: "Add [product] to order and ask if they want anything else"
→ Do NOT route to payment_worker yet!

**STAGE 2: DONE BROWSING** (route to sales_worker)
If user says:
- "No, that's all" / "Just that" / "Nothing else"
- "I'm done" / "That's everything" / "Proceed"

→ Route to `sales_worker` with task: "Show order summary and ask customer to confirm before checkout"

**STAGE 3: ORDER CONFIRMED → CHECKOUT** (route to payment_worker)
If user explicitly confirms after seeing order summary:
- "Yes, confirm" / "Confirm order" / "Looks good, proceed"
- "Yes" (in response to confirmation prompt)

→ Route to `payment_worker` to get delivery details and generate payment link

**CRITICAL: RECOGNIZE DELIVERY DETAILS**
If user provides information like:
- A name (e.g., "John Adebayo", "My name is...")
- A phone number (e.g., "08012345678", "+234...")
- An address (e.g., "15 Admiralty Way Lekki", "Deliver to Lagos")
- Any combination of the above

This is **DELIVERY DETAILS** for an ongoing order!
→ Route to `payment_worker` to process the delivery information and continue order.
→ Do NOT treat as off-topic or route to sales_worker!

**Available Workers:**
- `sales_worker`: Product search, explanation, visual analysis, general chat, ORDER BUILDING (add items, show summary)
- `support_worker`: Complaints, issues, returns, escalations (use for ANY negative/complaint)
- `admin_worker`: Stock checks, approvals (>25k), reporting
- `payment_worker`: Delivery calculation, payment links, CHECKOUT (after order confirmed), DELIVERY DETAILS

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

**Example 2 (Add to Order - NOT checkout!):**
User: "I'll take the Advanced Clinical Vitamin C Serum"
{
  "thinking": "User wants to add a product to their order. Add it and ask if they want more.",
  "plan": [{"id": "step1", "worker": "sales_worker", "task": "Add Advanced Clinical Vitamin C Serum to order and ask if they want anything else", "dependencies": [], "reason": "Add to order"}]
}

**Example 3 (Done Browsing - Show Summary):**
User: "No, that's all"
{
  "thinking": "User is done browsing. Show order summary and ask for confirmation.",
  "plan": [{"id": "step1", "worker": "sales_worker", "task": "Show order summary and ask customer to confirm before checkout", "dependencies": [], "reason": "Order summary"}]
}

**Example 4 (Confirmed - Checkout):**
User: "Yes, confirm"
{
  "thinking": "User confirmed their order. Process checkout.",
  "plan": [{"id": "step1", "worker": "payment_worker", "task": "Get delivery details and generate payment link", "dependencies": [], "reason": "Order confirmed"}]
}

**Example 5 (Delivery Details):**
User: "John Adebayo, 08012345678, 15 Admiralty Way Lekki, Lagos"
{
  "thinking": "User provided delivery details for their order. Continue order processing.",
  "plan": [{"id": "step1", "worker": "payment_worker", "task": "Process delivery details and generate payment link", "dependencies": [], "reason": "Delivery details provided"}]
}

**Business Rules:**
1. Simple queries = 1 step (sales_worker). Don't over-plan.
2. Orders > 25k need admin_worker approval.
3. Image → sales_worker first to analyze.
4. Calculate delivery before generating payment link.
5. **ADD TO ORDER → sales_worker (to build order and ask for more)**
6. **CHECKOUT → payment_worker (only AFTER user confirms order summary)**
"""


async def planner_agent_node(state: AgentState):
    """Creates execution plan from user message."""
    messages = state.get("messages", [])
    if not messages:
        return {"error": "No messages"}

    visual_context = state.get("visual_matches", "")
    order_data = state.get("order_data", {})
    ordered_items = state.get("ordered_items", [])
    
    system_prompt = PLANNER_SYSTEM_PROMPT
    if visual_context:
        system_prompt += f"\n(Visual Context: {visual_context})\n"
    
    # Inject active order context so planner knows about ongoing transactions
    if order_data or ordered_items:
        delivery_status = "PROVIDED" if order_data.get("delivery_details") else "NEEDED"
        system_prompt += f"\n### 🛒 ACTIVE ORDER CONTEXT\n"
        system_prompt += f"Items in cart: {len(ordered_items)} products\n"
        if order_data.get("total_amount"):
            system_prompt += f"Total amount: ₦{order_data.get('total_amount', 0):,.2f}\n"
        system_prompt += f"Delivery info: {delivery_status}\n"
        system_prompt += f"\n**CRITICAL**: If user just provided name/phone/address, this is delivery info for the ACTIVE ORDER above. Continue with payment link generation, do NOT restart the conversation!\n\n"

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

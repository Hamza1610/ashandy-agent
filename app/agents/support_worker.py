"""
Support Worker: Handles customer complaints, issues, and escalations.

Key principles:
1. Empathy-first: Acknowledge feelings before problem-solving
2. Incident tracking: Create ticket on complaint
3. STAR logging: Document Task, Action, Result for every ticket
4. Manager relay: Ask manager for order status, refunds, etc.
5. Resolution: Support can close simple tickets when customer confirms
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from app.services.incident_service import incident_service
from app.utils.brand_voice import WHATSAPP_FORMAT_RULES
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain.tools import tool
import logging

logger = logging.getLogger(__name__)


# ============ SUPPORT TOOLS ============

@tool
async def lookup_order_history(user_id: str) -> str:
    """Fetch recent orders for a customer to understand their complaint context."""
    from app.services.db_service import AsyncSessionLocal
    from sqlalchemy import text
    
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT id, product_info, total_amount, status, created_at
                FROM orders WHERE user_id = :user_id
                ORDER BY created_at DESC LIMIT 5
            """)
            result = await session.execute(query, {"user_id": user_id})
            orders = result.fetchall()
            
            if not orders:
                return "No previous orders found for this customer."
            
            output = "📦 *Recent Orders*\\n\\n"
            for o in orders:
                output += f"• Order #{str(o[0])[:8]} - ₦{o[2]:,.0f} ({o[3]})\\n"
            return output
            
    except Exception as e:
        logger.error(f"Order lookup error: {e}")
        return "Unable to fetch order history."


@tool
async def create_support_ticket(user_id: str, issue_summary: str) -> str:
    """Create a support ticket for tracking this customer's issue."""
    incident_id = await incident_service.create_incident(
        user_id=user_id,
        situation=issue_summary,
        task="Customer support request",
        status="OPEN"
    )
    
    if incident_id:
        return f"✅ Created ticket #{incident_id[:8]}. Manager has been notified."
    return "❌ Failed to create ticket. Please try again."


@tool
async def escalate_to_manager(user_id: str, incident_id: str, reason: str) -> str:
    """Escalate issue to manager when support worker cannot resolve."""
    from app.services.meta_service import meta_service
    from app.utils.config import settings
    
    # Update status
    await incident_service.update_status(incident_id, "ESCALATED")
    
    # Notify manager
    if settings.ADMIN_PHONE_NUMBERS and len(settings.ADMIN_PHONE_NUMBERS) > 0:
        message = (
            f"⚠️ *ESCALATION REQUIRED*\\n\\n"
            f"📋 Ticket: #{incident_id[:8]}\\n"
            f"👤 Customer: {user_id}\\n"
            f"📝 Reason: {reason}\\n\\n"
            f"Please contact the customer directly."
        )
        await meta_service.send_whatsapp_text(settings.ADMIN_PHONE_NUMBERS[0], message)
    else:
        logger.error(f"Cannot send escalation notification: No admin phone numbers configured")
    
    return (
        f"I've escalated this to our manager who will contact you directly. "
        f"Your ticket number is #{incident_id[:8]}. Thank you for your patience! 🙏"
    )


# Import new tools from support_tools.py
from app.tools.support_tools import (
    update_incident_star,
    relay_to_manager,
    confirm_customer_resolution
)

# ============ SUPPORT WORKER NODE ============

SUPPORT_TOOLS = [
    lookup_order_history,
    create_support_ticket,
    escalate_to_manager,
    update_incident_star,  # NEW: STAR logging
    relay_to_manager,  # NEW: Manager relay
    confirm_customer_resolution  # NEW: Resolution confirmation
]


async def support_worker_node(state: AgentState):
    """
    Handles customer support: complaints, issues, returns, escalations.
    
    Flow:
    1. Check for existing incident
    2. If new complaint: create ticket
    3. Empathy response + log STAR
    4. Relay to manager or escalate
    5. Mark resolved if customer confirms
    """
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses", {})
        
        # Extract last user message
        last_user_msg = ""
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                if hasattr(msg, 'content') and type(msg).__name__ == "HumanMessage":
                    last_user_msg = msg.content
                    break
        
        # SECURITY: Input validation and truncation
        from app.utils.input_validation import MAX_MESSAGE_LENGTH, MAX_INCIDENT_LENGTH
        from app.utils.sanitization import sanitize_message
        
        if len(last_user_msg) > MAX_MESSAGE_LENGTH:
            logger.warning(f"⚠️ Support worker: Input truncated for {user_id}: {len(last_user_msg)} chars → {MAX_MESSAGE_LENGTH}")
            last_user_msg = last_user_msg[:MAX_MESSAGE_LENGTH] + "... [Message truncated for safety]"
        
        # Sanitize message content
        last_user_msg = sanitize_message(last_user_msg)
        
        # Find active task
        current_task = None
        for step in plan:
            if step.get("worker") == "support_worker" and task_statuses.get(step.get("id")) == "in_progress":
                current_task = step
                break
        
        if not current_task:
            return {"worker_result": "No active task for support_worker."}
        
        task_desc = current_task.get("task", "")
        task_id = current_task.get("id")
        logger.info(f"🆘 SUPPORT WORKER: Handling '{task_desc}' (ID: {task_id})")
        
        # Check for existing incident
        existing_incident = await incident_service.get_open_incident_for_user(user_id)
        incident_context = ""
        
        if existing_incident:
            incident_context = f"""
### EXISTING INCIDENT
Ticket: #{existing_incident['id'][:8]}
Status: {existing_incident['status']}
Original issue: {existing_incident['situation'][:200]}

If this is a follow-up on the same issue, mention the ticket.
If this is a NEW issue, create a new ticket.
"""
        
        # Retry context
        retry_count = state.get("retry_counts", {}).get(task_id, 0)
        critique = state.get("reviewer_critique", "")
        retry_context = f"\\n⚠️ PREVIOUS ATTEMPT REJECTED: {critique}\\n" if retry_count > 0 else ""
        
        # Tools and LLM
        llm = get_llm(model_type="fast", temperature=0.3).bind_tools(SUPPORT_TOOLS)
        
        system_prompt = f"""You are the Customer Support Specialist for Ashandy Home of Cosmetics.

## YOUR MANDATE
Handle complaints, issues, and concerns with EMPATHY FIRST in a manager-in-loop workflow.

## TOOLS
- `lookup_order_history(user_id)`: Check customer's recent orders
- `create_support_ticket(user_id, issue_summary)`: Create tracking ticket  
- `update_incident_star(incident_id, task, action, result)`: **REQUIRED** - Log actions for audit
- `relay_to_manager(user_id, incident_id, question, suggested_responses)`: Ask manager, relay answer
- `escalate_to_manager(user_id, incident_id, reason)`: Full escalation for complex issues
- `confirm_customer_resolution(incident_id, resolution_summary, confirmed)`: Close simple tickets

## CURRENT TASK
{task_desc}
{incident_context}
{retry_context}

## MANAGER-IN-LOOP WORKFLOW

### 1. EMPATHY FIRST (ALWAYS)
Start with acknowledgment:
- "I'm so sorry to hear about this..." 😔
- "I completely understand your frustration..." 💕
- "Thank you for bringing this to our attention..." 🙏

### 2. CREATE TICKET
For every complaint: `create_support_ticket(user_id, issue_summary)`

### 3. LOG STAR IMMEDIATELY ⚠️ REQUIRED
After ticket: `update_incident_star(incident_id, task="[goal]", action="[what you did]")`

### 4. ROUTE TO MANAGER

**Order Status** ("Where is my order?"):
→ `relay_to_manager(user_id, incident_id, "Order status?", ["pending","confirmed","shipped","delivered"])`

**Refund Request** (ALL refunds = manager approval):
→ `relay_to_manager(user_id, incident_id, "Refund request: [reason]", ["approved","denied","need-proof"])`

**Complex Issues**:  
→ `escalate_to_manager(user_id, incident_id, "[detailed reason]")`

### 5. UPDATE STAR AFTER MANAGER
When manager responds:
→ `update_incident_star(incident_id, action="Manager said: [X]", result="[outcome]")`

### 6. RESOLUTION (Simple Only)

**CAN resolve:** Customer says "Thanks!" + Simple issue (tracking/status)
→ `confirm_customer_resolution(incident_id, "[summary]", customer_confirmed=True)`

**CANNOT resolve:** Refunds, damage claims, disputes (stay ESCALATED)

## CRITICAL POLICIES

**Refunds:** ALL manager-approved. NEVER say "I can process your refund"
**Returns:** 48 hours window. Outside window = ask manager for exception
**Non-Returnable:** Opened makeup/skincare, used brushes

{WHATSAPP_FORMAT_RULES}

Customer: {user_id}
"""

        conversation = [SystemMessage(content=system_prompt)] + messages[-5:]
        response = await llm.ainvoke(conversation)
        
        # Execute tools
        final_result = response.content or ""
        tool_evidence = []
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Support Worker calling tool: {name}")
                
                # Inject user_id if not provided
                if "user_id" not in args and name in ["lookup_order_history", "create_support_ticket", "escalate_to_manager", "relay_to_manager"]:
                    args["user_id"] = user_id
                
                tool_output = ""
                if name == "lookup_order_history":
                    tool_output = await lookup_order_history.ainvoke(args)
                elif name == "create_support_ticket":
                    tool_output = await create_support_ticket.ainvoke(args)
                elif name == "escalate_to_manager":
                    # Get incident ID from existing or most recent
                    if existing_incident:
                        args["incident_id"] = existing_incident["id"]
                    tool_output = await escalate_to_manager.ainvoke(args)
                elif name == "update_incident_star":
                    tool_output = await update_incident_star.ainvoke(args)
                elif name == "relay_to_manager":
                    tool_output = await relay_to_manager.ainvoke(args)
                elif name == "confirm_customer_resolution":
                    tool_output = await confirm_customer_resolution.ainvoke(args)
                
                tool_evidence.append({
                    "tool": name,
                    "args": args,
                    "output": str(tool_output)[:500]
                })
            
            # Pass tool outputs back to LLM for conversational formatting
            tool_outputs_text = ""
            for item in tool_evidence:
                tool_outputs_text += f"\\n{item['output']}"
            
            if tool_outputs_text.strip():
                formatting_prompt = f"""Format this support action result into a friendly response.

SUPPORT ACTION RESULTS:
{tool_outputs_text}

RULES:
- DO NOT introduce yourself (no "I'm Awéléwà" or "I'm your assistant")
- Start with empathy if there's an issue
- Explain what action was taken
- Be reassuring and professional
- Keep it under 250 chars
- End with reassurance or next steps
- NEVER show ticket IDs or technical data

GOOD EXAMPLE:
"I understand your concern! 💕 I've created a support ticket and our team will reach out within 24 hours. Is there anything else I can help with?"

NOW FORMAT THE RESPONSE:"""
                from app.services.llm_service import get_llm as get_formatting_llm
                format_response = await get_formatting_llm(model_type="fast", temperature=0.4).ainvoke(
                    [HumanMessage(content=formatting_prompt)]
                )
                final_result = format_response.content
            else:
                final_result = response.content
        
        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)]
        }
        
    except Exception as e:
        logger.error(f"Support Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error: {str(e)}"}

"""
Support Worker: Handles customer complaints, issues, and escalations.

Key principles:
1. Empathy-first: Acknowledge feelings before problem-solving
2. Incident tracking: Create ticket on complaint
3. Manager escalation: After first failed resolution
4. Handoff: Escalated issues go to manager, system returns to sales
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from app.services.incident_service import incident_service
from app.utils.brand_voice import WHATSAPP_FORMAT_RULES
from langchain_core.messages import SystemMessage, AIMessage
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
            
            output = "📦 *Recent Orders*\n\n"
            for o in orders:
                output += f"• Order #{str(o[0])[:8]} - ₦{o[2]:,.0f} ({o[3]})\n"
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
    if settings.ADMIN_PHONE_NUMBERS:
        message = (
            f"⚠️ *ESCALATION REQUIRED*\n\n"
            f"📋 Ticket: #{incident_id[:8]}\n"
            f"👤 Customer: {user_id}\n"
            f"📝 Reason: {reason}\n\n"
            f"Please contact the customer directly."
        )
        await meta_service.send_whatsapp_text(settings.ADMIN_PHONE_NUMBERS[0], message)
    
    return (
        f"I've escalated this to our manager who will contact you directly. "
        f"Your ticket number is #{incident_id[:8]}. Thank you for your patience! 🙏"
    )


# ============ SUPPORT WORKER NODE ============

SUPPORT_TOOLS = [lookup_order_history, create_support_ticket, escalate_to_manager]


async def support_worker_node(state: AgentState):
    """
    Handles customer support: complaints, issues, returns, escalations.
    
    Flow:
    1. Check for existing incident
    2. If new complaint: create ticket
    3. Empathy response + attempt resolution
    4. If cannot resolve: escalate to manager
    """
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses", {})
        
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

If this is a follow-up on the same issue, remind the manager.
If this is a NEW issue, create a new ticket.
"""
        
        # Retry context
        retry_count = state.get("retry_counts", {}).get(task_id, 0)
        critique = state.get("reviewer_critique", "")
        retry_context = f"\n⚠️ PREVIOUS ATTEMPT REJECTED: {critique}\n" if retry_count > 0 else ""
        
        # Tools and LLM
        llm = get_llm(model_type="fast", temperature=0.3).bind_tools(SUPPORT_TOOLS)
        
        system_prompt = f"""You are the Customer Support Specialist for Ashandy Home of Cosmetics.

## YOUR MANDATE
Handle complaints, issues, and concerns with EMPATHY FIRST.

## TOOLS
- `lookup_order_history(user_id)`: Check customer's recent orders
- `create_support_ticket(user_id, issue_summary)`: Create a tracking ticket
- `escalate_to_manager(user_id, incident_id, reason)`: Escalate unresolvable issues

## CURRENT TASK
{task_desc}
{incident_context}
{retry_context}

## GUIDELINES

### 1. EMPATHY FIRST
Start with acknowledgment:
- "I'm so sorry to hear about this..."
- "I completely understand your frustration..."
- "Thank you for bringing this to our attention..."

### 2. CREATE TICKET
For every new complaint, create a ticket using `create_support_ticket`.

### 3. ATTEMPT RESOLUTION
Common resolutions:
- Delivery delays → Check order status, provide update
- Wrong product → Apologize, offer exchange/return info
- Quality issue → Apologize, escalate for manager decision

### 4. ESCALATE WHEN NEEDED
If you cannot resolve (refunds, replacements, disputes), use `escalate_to_manager`.
Tell customer: "I've escalated this to our manager who will contact you directly."

### 5. AFTER ESCALATION
Do NOT continue handling the issue. The manager will take over directly.

{WHATSAPP_FORMAT_RULES}

## CONTEXT
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
                if "user_id" not in args:
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
                
                tool_evidence.append({
                    "tool": name,
                    "args": args,
                    "output": str(tool_output)[:500]
                })
                
                final_result += f"\n\n{tool_output}"
        
        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)]
        }
        
    except Exception as e:
        logger.error(f"Support Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error: {str(e)}"}

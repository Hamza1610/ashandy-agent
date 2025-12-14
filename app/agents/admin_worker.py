"""
Admin Worker: LLM-powered agent for Manager-facing operations.
Upgraded to System 3.0 with Llama 4 Scout brain.
"""
from app.state.agent_state import AgentState
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, AIMessage
from app.utils.config import settings

# Import all Admin tools
from app.tools.report_tool import generate_comprehensive_report, generate_weekly_report
from app.tools.incident_tools import report_incident
from app.tools.admin_tools import relay_message_to_customer, get_incident_context, resolve_incident
from app.tools.approval_tools import list_pending_approvals, approve_order, reject_order

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Define the tool list for the Admin Worker
ADMIN_TOOLS = [
    generate_comprehensive_report,
    list_pending_approvals,
    approve_order,
    reject_order,
    relay_message_to_customer,
    get_incident_context,
    resolve_incident,
    report_incident,
]

# Tool names for graceful refusal
ADMIN_TOOL_NAMES = [
    "generate_comprehensive_report",
    "list_pending_approvals", 
    "approve_order",
    "reject_order",
    "relay_message_to_customer",
    "get_incident_context",
    "resolve_incident",
    "report_incident",
]


async def admin_worker_node(state: AgentState):
    """
    Admin Worker: LLM-powered agent for Manager-facing operations.
    
    Uses Llama 4 Scout 17B for advanced reasoning.
    Executes tasks via tool calling with strict scope enforcement.
    """
    # --- PUB/SUB TASK RETRIEVAL ---
    plan = state.get("plan", [])
    task_statuses = state.get("task_statuses", {})
    
    # Find My Task
    current_step = None
    for step in plan:
        if step.get("worker") == "admin_worker" and task_statuses.get(step["id"]) == "in_progress":
            current_step = step
            break
    
    # Fallback: If Dispatcher sent us here but status state is lost
    if not current_step and not task_statuses and plan:
        for step in plan:
            if step.get("worker") == "admin_worker":
                current_step = step
                logger.info(f"Admin Worker: Recovered Task {step.get('id')} from plan.")
                break
    
    if not current_step:
        return {"worker_result": "No active task for admin_worker."}
        
    task_desc = current_step.get("task", "")
    task_id = current_step.get("id")
    
    logger.info(f"🛡️ ADMIN WORKER (LLM): Processing '{task_desc}' (ID: {task_id})")
    
    try:
        # --- CONTEXT EXTRACTION ---
        retry_count = state.get("retry_counts", {}).get(task_id, 0)
        critique = state.get("reviewer_critique", "")
        
        context_str = ""
        if retry_count > 0 and critique:
            context_str = f"\n⚠️ PREVIOUS ATTEMPT REJECTED. Fix this: {critique}\n"
        
        # Get pending approvals count for context
        pending_count = 0
        try:
            pending_result = await list_pending_approvals.ainvoke({})
            if "pending" in pending_result.lower():
                import re
                count_match = re.search(r'(\d+)', pending_result)
                if count_match:
                    pending_count = int(count_match.group(1))
        except:
            pass
        
        # --- LLM SETUP ---
        llm = ChatGroq(
            temperature=0.1,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        ).bind_tools(ADMIN_TOOLS)
        
        # --- SYSTEM PROMPT ---
        system_prompt = f"""You are the **Admin Operations Manager** for Ashandy Cosmetics.

## YOUR IDENTITY
- You report ONLY to the human Manager (via WhatsApp).
- You execute commands using a STRICT set of tools.
- If asked to do something OUTSIDE your tools, politely refuse.

## YOUR TOOLS (ONLY THESE)
1. `generate_comprehensive_report(start_date, end_date)`: Generate business report.
   - Accepts: ISO dates OR relative like "yesterday", "last week", "December 10th"
   - Examples: "report for yesterday", "report from Dec 1 to Dec 7"
   
2. `list_pending_approvals()`: List orders awaiting Manager approval.

3. `approve_order(customer_id)`: Approve a pending high-value order.
   - Extract customer phone number from context.

4. `reject_order(customer_id, reason)`: Reject order with reason.
   - Always include a clear reason.

5. `relay_message_to_customer(customer_id, message)`: Send message to customer.
   - Use when Manager says "Tell customer X...", "Inform user...", etc.
   - Extract the exact message to relay.

6. `get_incident_context(incident_id, user_id)`: Get details about a conflict/escalation.
   - Use when Manager asks about a complaint or issue.

7. `resolve_incident(incident_id, resolution)`: Mark incident as resolved.

8. `report_incident(...)`: Log a new incident.

## DATE HANDLING
- "Yesterday" = previous day
- "Last week" = past 7 days
- "December 10th" = specific date

## GRACEFUL REFUSAL
If asked to do something NOT in your tools, respond:
"I cannot perform that action. My available capabilities are: generating reports, managing order approvals, relaying messages to customers, and handling incidents."

Examples of things you CANNOT do:
- Add inventory
- Modify prices
- Delete customers
- Process refunds
- Send emails (only WhatsApp)

## CURRENT CONTEXT
Manager ID: {state.get('user_id', 'Unknown')}
Pending Approvals: {pending_count}
Current Date: {datetime.now().strftime('%Y-%m-%d')}
{context_str}

## YOUR TASK
{task_desc}
"""

        messages = [SystemMessage(content=system_prompt)]
        
        # --- INVOKE LLM ---
        response = await llm.ainvoke(messages)
        
        # --- EXECUTE TOOLS (ReAct Style) ---
        final_result = response.content or ""
        tool_evidence = []
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Admin Worker calling tool: {name} with args: {args}")
                
                tool_output = ""
                
                # Map tool calls to actual functions
                if name == "generate_comprehensive_report":
                    tool_output = await generate_comprehensive_report.ainvoke(args)
                elif name == "list_pending_approvals":
                    tool_output = await list_pending_approvals.ainvoke(args)
                elif name == "approve_order":
                    tool_output = await approve_order.ainvoke(args)
                elif name == "reject_order":
                    tool_output = await reject_order.ainvoke(args)
                elif name == "relay_message_to_customer":
                    tool_output = await relay_message_to_customer.ainvoke(args)
                elif name == "get_incident_context":
                    tool_output = await get_incident_context.ainvoke(args)
                elif name == "resolve_incident":
                    tool_output = await resolve_incident.ainvoke(args)
                elif name == "report_incident":
                    tool_output = await report_incident.ainvoke(args)
                else:
                    tool_output = f"Unknown tool: {name}"
                
                # Capture evidence
                tool_evidence.append({
                    "tool": name,
                    "args": args,
                    "output": str(tool_output)[:500]
                })
                
                final_result += f"\n\n{tool_output}"
        
        # If no tools called and no content, generate a refusal or clarification
        if not response.tool_calls and not final_result.strip():
            final_result = "I understand your request, but I need more specific instructions. What would you like me to do?"
        
        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)]
        }
        
    except Exception as e:
        logger.error(f"Admin Worker Error: {e}", exc_info=True)
        return {
            "worker_result": f"Error: {str(e)}",
            "messages": [AIMessage(content=f"Admin Error: {str(e)}")]
        }

async def admin_email_alert_node(state: AgentState):
    """
    Escalation Handler: Sends Email to Admin + Apology to User.
    Triggered when a task fails max retries.
    """
    error_msg = state.get("error", "Unknown system error")
    user_id = state.get("user_id")
    
    # 1. User Message (Graceful)
    user_reply = "Sorry, I couldn't process your request completely. Please try again or contact support."
    
    # 2. Admin Email (Implementation)
    if settings.SMTP_SERVER and settings.SMTP_USERNAME and settings.SMTP_PASSWORD and settings.ADMIN_EMAIL:
        try:
            import aiosmtplib
            from email.message import EmailMessage
            
            # Context for Admin
            critique = state.get("reviewer_critique", "N/A")
            plan = state.get("plan", [])
            
            # Find the failed step
            # logic: error_msg usually contains "Task {id} Failed..."
            failed_step = None
            failed_step_id = "unknown"
            for s in plan:
                if s.get("id") in error_msg:
                    failed_step = s
                    failed_step_id = s.get("id")
                    break
            
            task_desc = failed_step.get("task") if failed_step else "Unknown Task"
            worker_name = failed_step.get("worker") if failed_step else "Unknown Worker"
            
            email_body = f"""🚨 SYSTEM ALERT: AGENT FAILURE
            
User ID: {user_id}
Error Context: {error_msg}

--------------------------------------------------
❌ FAILURE DETAILS
--------------------------------------------------
• Failed Worker:  {worker_name.upper()}
• Task ID:        {failed_step_id}
• Assignment:     "{task_desc}"

--------------------------------------------------
🔍 REVIEWER CRITIQUE (Reason for Rejection):
{critique}
--------------------------------------------------

Please intervene immediately.
"""
            
            msg = EmailMessage()
            msg.set_content(email_body)
            msg['Subject'] = f"🚨 ASHANDY ALERT: {worker_name.upper()} Failed (User {user_id})"
            msg['From'] = settings.SMTP_USERNAME
            msg['To'] = settings.ADMIN_EMAIL
            
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_SERVER,
                port=settings.SMTP_PORT,
                start_tls=True,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD
            )
            logger.info(f"Escalation email sent to {settings.ADMIN_EMAIL}")
        except Exception as e:
            logger.error(f"Failed to send escalation email: {e}")
    else:
        logger.warning("SMTP not configured. Skipping email alert.")
        
    logger.critical(f"🚨 ADMIN ALERT: Escalation triggered for User {user_id}. Reason: {error_msg}")
    
    return {
        "messages": [AIMessage(content=user_reply)]
    }

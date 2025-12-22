"""
Admin Worker: Reports, high-value approvals, broadcasting, incident management.
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from app.utils.config import settings
from app.utils.input_validation import MAX_MESSAGE_LENGTH
from app.utils.sanitization import sanitize_message
from app.utils.brand_voice import WHATSAPP_FORMAT_RULES
from app.tools.report_tool import generate_comprehensive_report, generate_weekly_report
from app.tools.incident_tools import report_incident
from app.tools.admin_tools import relay_message_to_customer, get_incident_context, resolve_incident, get_top_customers
from app.tools.approval_tools import list_pending_approvals, approve_order, reject_order
from app.tools.sms_tools import notify_manager
from app.tools.manual_payment_tools import get_pending_manual_payments, confirm_manual_payment, reject_manual_payment
from app.tools.order_utility_tools import get_recent_orders, search_order_by_customer, view_order_details
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

ADMIN_TOOLS = [
    # Reports
    generate_comprehensive_report,
    # Order approvals
    list_pending_approvals,
    approve_order,
    reject_order,
    # Manual payment verification
    get_pending_manual_payments,
    confirm_manual_payment,
    reject_manual_payment,
    # Order utilities
    get_recent_orders,
    search_order_by_customer,
    view_order_details,
    # Customer messaging
    relay_message_to_customer,
    notify_manager,
    # Incident management
    get_incident_context,
    resolve_incident,
    report_incident,
    # Analytics
    get_top_customers,
]


async def admin_worker_node(state: AgentState):
    """Executes admin tasks: reports, approvals, customer messaging, incident handling."""
    plan = state.get("plan", [])
    task_statuses = state.get("task_statuses", {})
    messages = state.get("messages", [])
    user_id = state.get("user_id", "Unknown")
    
    # Find active task
    current_step = None
    for step in plan:
        if step.get("worker") == "admin_worker" and task_statuses.get(step.get("id")) == "in_progress":
            current_step = step
            break
    
    if not current_step and not task_statuses and plan:
        for step in plan:
            if step.get("worker") == "admin_worker":
                current_step = step
                break
    
    if not current_step:
        return {"worker_result": "No active task for admin_worker."}
        
    task_desc = current_step.get("task", "")
    task_id = current_step.get("id")
    logger.info(f"🛡️ ADMIN WORKER: Processing '{task_desc}' (ID: {task_id})")

    # Extract last user message for sanitization
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break
    
    # SECURITY: Input validation and truncation
    if len(last_user_msg) > MAX_MESSAGE_LENGTH:
        logger.warning(f"⚠️ Admin worker: Input truncated for {user_id}: {len(last_user_msg)} chars → {MAX_MESSAGE_LENGTH}")
        last_user_msg = last_user_msg[:MAX_MESSAGE_LENGTH] + "... [Message truncated for safety]"
    
    # Sanitize message content
    task_desc = sanitize_message(task_desc) # Sanitize the task description which might contain user input
    last_user_msg = sanitize_message(last_user_msg) # Sanitize the raw user message
    
    try:
        # Retry context
        retry_count = state.get("retry_counts", {}).get(task_id, 0)
        critique = state.get("reviewer_critique", "")
        context_str = f"\n⚠️ PREVIOUS ATTEMPT REJECTED: {critique}\n" if retry_count > 0 and critique else ""
        
        # Pending approvals count
        pending_count = 0
        try:
            pending_result = await list_pending_approvals.ainvoke({})
            import re
            match = re.search(r'(\d+)', pending_result)
            pending_count = int(match.group(1)) if match else 0
        except:
            pass
        
        llm = get_llm(model_type="fast", temperature=0.1).bind_tools(ADMIN_TOOLS)
        
        system_prompt = f"""You are the Admin Operations Manager for Ashandy Cosmetics.
## 📋 AVAILABLE TOOLS ({len(ADMIN_TOOLS)} tools)
**Order Management:**
- `get_recent_orders(limit, hours)` - View recent orders
- `search_order_by_customer(customer_phone)` - Find customer's orders  
- `view_order_details(order_id)` - See full order details
- `list_pending_approvals()` - High-value orders awaiting approval
- `approve_order(customer_id)` - Approve pending order
- `reject_order(customer_id, reason)` - Reject with reason
**Manual Payment Verification:**
- `get_pending_manual_payments()` - Bank transfers awaiting verification
- `confirm_manual_payment(customer_id, amount, reference, notes)` - Confirm payment
- `reject_manual_payment(customer_id, reference, reason)` - Reject payment
**Communication:**
- `relay_message_to_customer(customer_id, message)` - Send WhatsApp
- `notify_manager(order_id, customer_name, items, total, address)` - Order notification
**Reports:**
- `generate_comprehensive_report(start_date, end_date)` - Business PDF
- `get_top_customers(period, limit)` - Best customers
**Incidents:**
- `get_incident_context()` / `resolve_incident()` / `report_incident()` - Incident mgmt
## 💬 INPUT TEMPLATES (Show manager EXACTLY this when they make errors)
**For Manual Payment Verification:**
To see pending: "Show pending manual payments"
To confirm:
Format: confirm payment for [phone], amount [number], reference [ref]
Example: confirm payment for 2348012345678, amount 5000, reference 2348012345678
To reject:
Format: reject payment for [phone], reference [ref], reason [why]
Example: reject payment for 2348012345678, reference 2348012345678, reason: Screenshot fake
**For Order Approvals:**
To see pending: "Show pending approvals"
To approve:
Format: approve order for [phone]
Example: approve order for 2348012345678
To reject:
Format: reject order for [phone], reason [why]
Example: reject order for 2348012345678, reason: Details incomplete
**For Searching Orders:**
Recent: "Show recent orders" or "Last 24 hours"
Customer: "Find orders for 2348012345678"
Details: "View order 12345"
## 🔒 SECURITY
1. Only whitelisted admins can use these commands
2. Approvals are logged and auditable  
3. Never share customer data with unauthorized users
## CONTEXT
Manager: {state.get('user_id', 'Unknown')} | Pending Approvals: {pending_count} | Date: {datetime.now().strftime('%Y-%m-%d')}
{context_str}
## TASK
{task_desc}
**IMPORTANT:** If manager's input format is wrong, show the relevant template above and ask to retry.
"""

        # Tool enforcement
        from app.utils.tool_enforcement import extract_required_tools_from_task, build_tool_enforcement_message
        required_tools = extract_required_tools_from_task(task_desc, "admin_worker")
        if required_tools:
            system_prompt += build_tool_enforcement_message(required_tools)
        
        response = await llm.ainvoke([SystemMessage(content=system_prompt)])
        final_result = response.content or ""
        tool_evidence = []
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Admin Worker calling tool: {name}")
                
                tool_output = ""
                if name == "generate_comprehensive_report":
                    tool_output = await generate_comprehensive_report.ainvoke(args)
                elif name == "list_pending_approvals":
                    tool_output = await list_pending_approvals.ainvoke(args)
                elif name == "approve_order":
                    tool_output = await approve_order.ainvoke(args)
                elif name == "reject_order":
                    tool_output = await reject_order.ainvoke(args)
                elif name == "get_pending_manual_payments":
                    tool_output = await get_pending_manual_payments.ainvoke(args)
                elif name == "confirm_manual_payment":
                    tool_output = await confirm_manual_payment.ainvoke(args)
                elif name == "reject_manual_payment":
                    tool_output = await reject_manual_payment.ainvoke(args)
                elif name == "get_recent_orders":
                    tool_output = await get_recent_orders.ainvoke(args)
                elif name == "search_order_by_customer":
                    tool_output = await search_order_by_customer.ainvoke(args)
                elif name == "view_order_details":
                    tool_output = await view_order_details.ainvoke(args)
                elif name == "relay_message_to_customer":
                    tool_output = await relay_message_to_customer.ainvoke(args)
                elif name == "notify_manager":
                    tool_output = await notify_manager.ainvoke(args)
                elif name == "get_incident_context":
                    tool_output = await get_incident_context.ainvoke(args)
                elif name == "resolve_incident":
                    tool_output = await resolve_incident.ainvoke(args)
                elif name == "report_incident":
                    tool_output = await report_incident.ainvoke(args)
                elif name == "get_top_customers":
                    tool_output = await get_top_customers.ainvoke(args)
                else:
                    tool_output = f"Unknown tool: {name}"
                
                tool_evidence.append({"tool": name, "args": args, "output": str(tool_output)[:500]})
                final_result += f"\n\n{tool_output}"
        
        if not response.tool_calls and not final_result.strip():
            final_result = "I need more specific instructions. What would you like me to do?"
        
        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)]
        }
        
    except Exception as e:
        logger.error(f"Admin Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error: {str(e)}", "messages": [AIMessage(content=f"Admin Error: {str(e)}")]}


async def admin_email_alert_node(state: AgentState):
    """Escalation handler: Sends email to admin when task fails max retries."""
    error_msg = state.get("error", "Unknown system error")
    user_id = state.get("user_id")
    user_reply = "Sorry, I couldn't process your request. Please try again or contact support."
    
    if settings.SMTP_SERVER and settings.SMTP_USERNAME and settings.SMTP_PASSWORD and settings.ADMIN_EMAIL:
        try:
            import aiosmtplib
            from email.message import EmailMessage
            
            critique = state.get("reviewer_critique", "N/A")
            plan = state.get("plan", [])
            
            failed_step = next((s for s in plan if s.get("id") in error_msg), None)
            task_desc = failed_step.get("task") if failed_step else "Unknown Task"
            worker_name = failed_step.get("worker") if failed_step else "Unknown Worker"
            
            email_body = f"""🚨 SYSTEM ALERT: AGENT FAILURE
            
User ID: {user_id}
Error: {error_msg}

❌ FAILURE DETAILS
• Worker: {worker_name.upper()}
• Task: "{task_desc}"

🔍 REVIEWER CRITIQUE:
{critique}

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
        
    logger.critical(f"🚨 ADMIN ALERT: Escalation for User {user_id}. Reason: {error_msg}")
    return {"messages": [AIMessage(content=user_reply)]}

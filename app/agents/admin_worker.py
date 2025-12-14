from app.state.agent_state import AgentState

from app.tools.report_tool import generate_weekly_report
from app.tools.incident_tools import report_incident
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def admin_worker_node(state: AgentState):
    """
    Admin Worker: Executes Administrative, Inventory, and Reporting Tasks.
    
    Inputs: 
    - state['plan'] + state['task_statuses']
    
    Outputs:
    - worker_result
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
    
    if not current_step:
        return {"worker_result": "No active task."}
        
    task_desc = current_step.get("task", "").lower()
    task_id = current_step.get("id")
    
    logger.info(f"🛡️ ADMIN WORKER: Processing '{task_desc}' (ID: {task_id})")
    
    response_text = "Task completed."
    
    try:
        # 1. STOCK CHECK
        if "stock" in task_desc and "check" in task_desc:
             # Refactored: We no longer query local DB for total count.
             # If specific product stock is needed, it should be a Sales Worker task.
             # If "Inventory Count" is requested, redirect to POS.
             response_text = "Stock Check: functionality has moved. Please use 'search [product]' to check specific stock, or view the PHPPOS Dashboard for total inventory reports."

        # 2. GENERATE REPORT
        elif "report" in task_desc or "/report" in task_desc:
             date_str = datetime.now().strftime("%Y-%m-%d")
             result = await generate_weekly_report.ainvoke(date_str)
             response_text = result

        # 3. SYNC INSTAGRAM
        elif "sync" in task_desc or "ingest" in task_desc:
             from app.services.ingestion_service import ingestion_service
             result = await ingestion_service.sync_instagram_products(limit=10)
             response_text = f"🔄 Sync Result: {result}"

             # 4. INCIDENT REPORT / HANDOVER
        elif "incident" in task_desc or "handover" in task_desc or "report user" in task_desc:
             user_id = state.get("user_id")
             # Parse STAR fields from context or default
             await report_incident.ainvoke({
                 "situation": f"User Request/Complaint: {task_desc}",
                 "task": "Handover to Human Manager",
                 "action": "Bot triggered Admin Alert",
                 "result": "Pending Manager Review",
                 "status": "ESCALATED",
                 "user_id": user_id
             })
             response_text = "Incident reported. Manager notified."

        # 5. APPROVAL REQUEST (>25k) (Outgoing)
        elif "approval" in task_desc and "request" in task_desc:
             from app.tools.approval_tools import request_order_approval
             # Try to extract amount and items from task desc or state
             # Ideally Planner provides structured args, but we parse text for now
             import re
             amount_match = re.search(r'(\d+)k?', task_desc)
             amount = float(amount_match.group(1)) * 1000 if amount_match else 25000.0
             
             user_id = state.get("user_id")
             await request_order_approval.ainvoke({
                 "user_id": user_id,
                 "amount": amount,
                 "items_summary": "High Value Items (See chat)"
             })
             response_text = "Approval request sent to Manager. Please wait."

        # 6. MANAGER ACTIONS (Incoming from Planner)
        
        # A. LIST PENDING
        elif "list" in task_desc and "pending" in task_desc:
             from app.tools.approval_tools import list_pending_approvals
             tool_res = await list_pending_approvals.ainvoke({})
             response_text = tool_res
             
        # B. REJECT ORDER
        elif "reject" in task_desc or "decline" in task_desc or "out of stock" in task_desc:
             from app.tools.approval_tools import reject_order
             # Extract reason from task_desc (e.g., "Reject user because out of stock")
             # We'll just pass the full desc as reason context if specific parsing is hard
             
             # Attempt to extract refined target user if present
             parts = task_desc.split()
             target_user = None
             for p in parts:
                 if p.startswith("+") or (p.startswith("0") and len(p) >= 11):
                     target_user = p
                     break
            
             reason = task_desc.replace("reject", "").replace("order", "").replace(str(target_user), "").strip()
             if not reason: reason = "Manager declined"
             
             tool_res = await reject_order.ainvoke({"target_user_id": target_user, "reason": reason})
             response_text = f"Rejection Action: {tool_res}"

        # C. APPROVE ORDER
        elif "approve" in task_desc or "confirm" in task_desc or "yes" in task_desc:
             from app.tools.approval_tools import approve_order
             
             # Attempt to extract refined target user if present
             parts = task_desc.split()
             target_user = None
             for p in parts:
                 if p.startswith("+") or (p.startswith("0") and len(p) >= 11):
                     target_user = p
                     break
            
             # Call tool (it handles the fallback to cache if target_user is None)
             tool_res = await approve_order.ainvoke({"target_user_id": target_user})
             response_text = f"Approval Action: {tool_res}"
        
             response_text = f"Admin processed task: {task_desc}"
             
             response_text = f"Admin processed task: {task_desc}"
             
        # CAPTURE EVIDENCE (Admin uses manual tool calls, so we construct this)
        # Note: In a cleaner refactor, we'd wrap these tool calls to auto-log. 
        # For now, we retrospectively log the successful action.
        tool_evidence = [{
            "tool": "admin_action", # Generic name for manual admin calls
            "args": {"task": task_desc},
            "output": str(response_text)[:500] 
        }]

        from langchain_core.messages import AIMessage
        return {
            "worker_outputs": {task_id: response_text},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=response_text)]
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

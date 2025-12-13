from app.state.agent_state import AgentState

from app.tools.report_tool import generate_weekly_report
from app.tools.incident_tools import report_incident
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def admin_worker_node(state: AgentState):
    """
    Admin Worker:Executes Administrative, Inventory, and Reporting Tasks.
    
    Inputs: 
    - state['plan'][state['current_step_index']]
    
    Outputs:
    - worker_result
    """
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    
    if idx >= len(plan):
        return {"worker_result": "No task."}
        
    current_step = plan[idx]
    task_desc = current_step.get("task", "").lower()
    
    logger.info(f"🛡️ ADMIN WORKER: Processing '{task_desc}'")
    
    response_text = "Task completed."
    
    try:
        # 1. STOCK CHECK
        if "stock" in task_desc and "check" in task_desc:
             from app.services.db_service import AsyncSessionLocal
             from sqlalchemy import text
             
             async with AsyncSessionLocal() as session:
                 result = await session.execute(text("SELECT COUNT(*) FROM products"))
                 count = result.scalar()
             response_text = f"Stock Check: {count} products found in database."

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
        
        else:
             response_text = f"Admin processed task: {task_desc}"
             
        return {"worker_result": response_text}
        
    except Exception as e:
        logger.error(f"Admin Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error: {str(e)}"}

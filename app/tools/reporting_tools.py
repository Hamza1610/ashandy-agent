from langchain.tools import tool
from app.services.meta_service import meta_service
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

@tool
async def report_incident(situation: str, task: str, action: str, result: str, status: str, user_id: str):
    """
    Reports an interaction log to the Manager using the STAR methodology.
    Use this when a complaint is handled (Resolved) OR when it cannot be handled (Escalated).
    
    Args:
        situation: What was the problem/complaint?
        task: What needed to be done?
        action: What did you (the Agent) do?
        result: What was the outcome? (Customer satisfied? Or still angry?)
        status: 'RESOLVED' (if fixed) or 'ESCALATED' (if requires manager).
        user_id: The customer's phone number or ID.
    """
    logger.info(f"Reporting Incident: {status} - {situation}")
    
    if not settings.ADMIN_PHONE_NUMBERS:
        return "Admin phone number not configured."

    manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
    
    emoji = "✅" if status.upper() == "RESOLVED" else "🚨"
    
    message = (
        f"{emoji} *INCIDENT REPORT ({status})*\n"
        f"👤 *Customer:* {user_id}\n"
        f"--------------------------------\n"
        f"📝 *Situation:* {situation}\n"
        f"🎯 *Task:* {task}\n"
        f"⚡ *Action:* {action}\n"
        f"🏁 *Result:* {result}\n"
        f"--------------------------------"
    )
    
    await meta_service.send_whatsapp_text(manager_phone, message)
    
    return "Report sent to manager."

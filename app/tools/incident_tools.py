"""
Incident Tools: STAR methodology reporting for escalations and resolutions.
"""
from langchain.tools import tool
from app.services.meta_service import meta_service
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)


@tool
async def report_incident(situation: str, task: str, action: str, result: str, status: str, user_id: str):
    """Report incident to Manager using STAR methodology. status: 'RESOLVED' or 'ESCALATED'."""
    logger.info(f"Incident: {status} - {situation}")
    
    if not settings.ADMIN_PHONE_NUMBERS:
        return "Admin phone not configured."

    emoji = "✅" if status.upper() == "RESOLVED" else "🚨"
    message = (
        f"{emoji} *INCIDENT ({status})*\n"
        f"👤 {user_id}\n"
        f"📝 *Situation:* {situation}\n"
        f"🎯 *Task:* {task}\n"
        f"⚡ *Action:* {action}\n"
        f"🏁 *Result:* {result}"
    )
    
    await meta_service.send_whatsapp_text(settings.ADMIN_PHONE_NUMBERS[0], message)
    return "Report sent to manager."

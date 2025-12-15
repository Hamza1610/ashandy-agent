"""
Admin Tools: Manager-facing tools for customer messaging and incident management.
"""
from langchain_core.tools import tool
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.services.meta_service import meta_service
import logging

logger = logging.getLogger(__name__)


@tool
async def relay_message_to_customer(customer_id: str, message: str) -> str:
    """Send a message to a customer via WhatsApp."""
    try:
        if not customer_id or not message:
            return "Error: Both customer_id and message are required."
        
        clean_id = customer_id.replace(" ", "").replace("-", "")
        if not clean_id.startswith("+"):
            clean_id = "+" + clean_id
        
        result = await meta_service.send_whatsapp_message(recipient_id=clean_id, message_text=message)
        
        if result:
            logger.info(f"Message relayed to {clean_id}")
            return f"✅ Message sent to {clean_id}: '{message}'"
        return f"❌ Failed to send message to {clean_id}."
            
    except Exception as e:
        logger.error(f"Relay message error: {e}")
        return f"Error: {str(e)}"


@tool
async def get_incident_context(incident_id: str = None, user_id: str = None) -> str:
    """Get incident details for Manager review. Returns STAR format report."""
    try:
        async with AsyncSessionLocal() as session:
            if incident_id:
                query = text("SELECT * FROM incidents WHERE id::text = :id")
                result = await session.execute(query, {"id": incident_id})
            elif user_id:
                query = text("SELECT * FROM incidents WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 5")
                result = await session.execute(query, {"user_id": user_id})
            else:
                query = text("SELECT * FROM incidents WHERE status IN ('OPEN', 'ESCALATED') ORDER BY created_at DESC LIMIT 5")
                result = await session.execute(query)
            
            rows = result.fetchall()
            if not rows:
                return "No incidents found."
            
            output = "📋 **Incident Report(s)**\n\n"
            for row in rows:
                r = dict(row._mapping)
                output += f"""---
**ID**: {r.get('id', 'N/A')} | **User**: {r.get('user_id', 'Unknown')} | **Status**: {r.get('status', 'N/A')}
**STAR**: Situation: {r.get('situation', 'N/A')} | Task: {r.get('task', 'N/A')} | Action: {r.get('action', 'N/A')} | Result: {r.get('result', 'N/A')}
"""
            return output
            
    except Exception as e:
        logger.error(f"Get incident error: {e}")
        return f"Error: {str(e)}"


@tool
async def resolve_incident(incident_id: str, resolution: str) -> str:
    """Mark an incident as resolved with a resolution note."""
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                UPDATE incidents SET status = 'RESOLVED', result = :resolution, resolved_at = NOW()
                WHERE id::text = :id RETURNING id
            """)
            result = await session.execute(query, {"id": incident_id, "resolution": resolution})
            await session.commit()
            
            if result.fetchone():
                return f"✅ Incident {incident_id} marked as RESOLVED."
            return f"❌ Incident {incident_id} not found."
                
    except Exception as e:
        logger.error(f"Resolve incident error: {e}")
        return f"Error: {str(e)}"

"""
Admin Tools: Manager-facing tools for the Admin Worker.
"""
from langchain_core.tools import tool
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.services.meta_service import meta_service
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@tool
async def relay_message_to_customer(customer_id: str, message: str) -> str:
    """
    Send a message to a specific customer via WhatsApp.
    
    Use this when the Manager says "Tell customer X..." or "Inform user about..."
    
    Args:
        customer_id: The customer's WhatsApp number (e.g., "+2348012345678")
        message: The message to send to the customer
    
    Returns:
        Confirmation of message sent or error
    """
    try:
        if not customer_id or not message:
            return "Error: Both customer_id and message are required."
        
        # Clean the customer ID
        clean_id = customer_id.replace(" ", "").replace("-", "")
        if not clean_id.startswith("+"):
            clean_id = "+" + clean_id
        
        # Send via Meta service
        result = await meta_service.send_whatsapp_message(
            recipient_id=clean_id,
            message_text=message
        )
        
        if result:
            logger.info(f"Message relayed to {clean_id}: {message[:50]}...")
            return f"✅ Message sent to {clean_id}: '{message}'"
        else:
            return f"❌ Failed to send message to {clean_id}. Please try again."
            
    except Exception as e:
        logger.error(f"Relay message error: {e}")
        return f"Error sending message: {str(e)}"


@tool
async def get_incident_context(incident_id: str = None, user_id: str = None) -> str:
    """
    Get details about an incident or escalation for the Manager to review.
    
    Use this when the Manager asks about a conflict, complaint, or escalation.
    
    Args:
        incident_id: Optional specific incident ID
        user_id: Optional user ID to find their incidents
    
    Returns:
        Incident details in STAR format (Situation, Task, Action, Result)
    """
    try:
        async with AsyncSessionLocal() as session:
            if incident_id:
                query = text("""
                    SELECT * FROM incidents WHERE id::text = :id
                """)
                result = await session.execute(query, {"id": incident_id})
            elif user_id:
                query = text("""
                    SELECT * FROM incidents 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
                result = await session.execute(query, {"user_id": user_id})
            else:
                # Get most recent open incidents
                query = text("""
                    SELECT * FROM incidents 
                    WHERE status IN ('OPEN', 'ESCALATED')
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
                result = await session.execute(query)
            
            rows = result.fetchall()
            
            if not rows:
                return "No incidents found matching the criteria."
            
            output = "📋 **Incident Report(s)**\n\n"
            for row in rows:
                row_dict = dict(row._mapping)
                output += f"""
---
**ID**: {row_dict.get('id', 'N/A')}
**User**: {row_dict.get('user_id', 'Unknown')}
**Status**: {row_dict.get('status', 'N/A')}
**Created**: {row_dict.get('created_at', 'N/A')}

**STAR Report:**
- **Situation**: {row_dict.get('situation', 'N/A')}
- **Task**: {row_dict.get('task', 'N/A')}
- **Action**: {row_dict.get('action', 'N/A')}
- **Result**: {row_dict.get('result', 'N/A')}
"""
            return output
            
    except Exception as e:
        logger.error(f"Get incident context error: {e}")
        return f"Error retrieving incident: {str(e)}"


@tool
async def resolve_incident(incident_id: str, resolution: str) -> str:
    """
    Mark an incident as resolved with a resolution note.
    
    Args:
        incident_id: The incident ID to resolve
        resolution: The resolution description
    
    Returns:
        Confirmation of resolution
    """
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                UPDATE incidents 
                SET status = 'RESOLVED', 
                    result = :resolution,
                    resolved_at = NOW()
                WHERE id::text = :id
                RETURNING id
            """)
            result = await session.execute(query, {
                "id": incident_id,
                "resolution": resolution
            })
            await session.commit()
            
            if result.fetchone():
                return f"✅ Incident {incident_id} marked as RESOLVED."
            else:
                return f"❌ Incident {incident_id} not found."
                
    except Exception as e:
        logger.error(f"Resolve incident error: {e}")
        return f"Error resolving incident: {str(e)}"

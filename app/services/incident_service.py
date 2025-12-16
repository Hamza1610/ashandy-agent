"""
Incident Service: Unified incident/complaint tracking.

Flow:
1. Customer complains → create_incident() → DB + notify manager
2. Customer references again → remind_manager_of_incident()
3. Manager resolves → resolve_incident() → notify customer
4. Further discussion → direct to manager, system returns to sales
"""
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.services.meta_service import meta_service
from app.utils.config import settings
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class IncidentService:
    """Manages customer complaints and support incidents."""
    
    async def create_incident(
        self,
        user_id: str,
        situation: str,
        task: str = "",
        action: str = "",
        status: str = "OPEN"
    ) -> Optional[str]:
        """
        Create new incident in DB and notify manager.
        
        Returns: incident_id (UUID string) or None on failure
        """
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    INSERT INTO incidents (user_id, situation, task, action, status)
                    VALUES (:user_id, :situation, :task, :action, :status)
                    RETURNING id::text
                """)
                result = await session.execute(query, {
                    "user_id": user_id,
                    "situation": situation[:1000],  # Truncate if too long
                    "task": task,
                    "action": action,
                    "status": status
                })
                incident_id = result.scalar_one()
                await session.commit()
                
                logger.info(f"Created incident {incident_id} for user {user_id}")
                
                # Notify manager
                await self._notify_manager_new_incident(user_id, situation, incident_id)
                
                return incident_id
                
        except Exception as e:
            logger.error(f"Failed to create incident: {e}")
            return None
    
    async def get_open_incident_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent open/escalated incident for a user."""
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT id::text, situation, status, created_at
                    FROM incidents 
                    WHERE user_id = :user_id AND status IN ('OPEN', 'ESCALATED')
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = await session.execute(query, {"user_id": user_id})
                row = result.fetchone()
                
                if row:
                    return {
                        "id": row[0],
                        "situation": row[1],
                        "status": row[2],
                        "created_at": row[3]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get incident for user: {e}")
            return None
    
    async def update_status(self, incident_id: str, status: str) -> bool:
        """Update incident status (OPEN, ESCALATED, IN_PROGRESS, RESOLVED)."""
        try:
            async with AsyncSessionLocal() as session:
                resolved_at = "NOW()" if status == "RESOLVED" else "NULL"
                query = text(f"""
                    UPDATE incidents 
                    SET status = :status, resolved_at = {resolved_at}
                    WHERE id::text = :id
                """)
                result = await session.execute(query, {"id": incident_id, "status": status})
                await session.commit()
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to update incident status: {e}")
            return False
    
    async def resolve_and_notify_customer(
        self, 
        incident_id: str, 
        resolution: str,
        customer_id: str
    ) -> bool:
        """
        Mark incident as resolved and notify the customer.
        Called when manager marks an issue as resolved.
        """
        try:
            # Update DB
            async with AsyncSessionLocal() as session:
                query = text("""
                    UPDATE incidents 
                    SET status = 'RESOLVED', result = :resolution, resolved_at = NOW()
                    WHERE id::text = :id
                """)
                result = await session.execute(query, {
                    "id": incident_id, 
                    "resolution": resolution
                })
                await session.commit()
                
                if result.rowcount == 0:
                    return False
            
            # Notify customer
            customer_message = (
                f"✅ *Issue Update*\n\n"
                f"I've checked with the manager regarding your concern. "
                f"The manager has confirmed that this has been resolved.\n\n"
                f"*Resolution:* {resolution}\n\n"
                f"If you have any other questions or need assistance with our products, "
                f"I'm here to help! 💄✨"
            )
            await meta_service.send_whatsapp_text(customer_id, customer_message)
            
            logger.info(f"Resolved incident {incident_id} and notified customer {customer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve incident: {e}")
            return False
    
    async def remind_manager_of_incident(self, user_id: str, incident_id: str, new_message: str):
        """
        Send reminder to manager when customer references an existing incident.
        """
        if not settings.ADMIN_PHONE_NUMBERS:
            logger.warning("No admin phone configured for incident reminder")
            return
        
        message = (
            f"🔔 *INCIDENT REMINDER*\n\n"
            f"Customer {user_id} has followed up on their issue:\n"
            f"📋 Ticket: #{incident_id[:8]}\n"
            f"💬 New message: \"{new_message[:200]}...\"\n\n"
            f"Please respond directly to the customer."
        )
        
        await meta_service.send_whatsapp_text(
            settings.ADMIN_PHONE_NUMBERS[0], 
            message
        )
    
    async def _notify_manager_new_incident(self, user_id: str, situation: str, incident_id: str):
        """Internal: Notify manager of new incident."""
        if not settings.ADMIN_PHONE_NUMBERS:
            logger.warning("No admin phone configured for incident notification")
            return
        
        message = (
            f"🚨 *NEW SUPPORT TICKET*\n\n"
            f"📋 Ticket: #{incident_id[:8]}\n"
            f"👤 Customer: {user_id}\n"
            f"📝 Issue: {situation[:300]}\n\n"
            f"Awéléwà is handling. Reply 'resolve {incident_id[:8]} [resolution]' to close."
        )
        
        await meta_service.send_whatsapp_text(
            settings.ADMIN_PHONE_NUMBERS[0],
            message
        )


# Singleton instance
incident_service = IncidentService()

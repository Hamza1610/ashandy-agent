"""
Support Tools: Manager-in-loop workflow with STAR incident tracking.

Tools:
- update_incident_star: Log Task/Action/Result for audit trail
- relay_to_manager: Send queries to manager via WhatsApp
- confirm_customer_resolution: Mark simple issues resolved
"""
from langchain.tools import tool
from app.services.db_service import AsyncSessionLocal
from app.services.incident_service import incident_service
from app.services.meta_service import meta_service
from app.utils.config import settings
from sqlalchemy import text
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@tool
async def update_incident_star(
    incident_id: str,
    task: str,
    action: str,
    result: str = ""
) -> str:
    """
    Update STAR fields (Situation, Task, Action, Result) for incident tracking.
    
    Call this after taking any support action to maintain audit trail.
    
    Args:
        incident_id: UUID of the incident
        task: What you're trying to accomplish (e.g., "Determine order delivery status")
        action: What you did (e.g., "Relayed query to manager for order status")
        result: Outcome if known (e.g., "Manager confirmed order shipped")
        
    Returns:
        Confirmation message
        
    Example:
        await update_incident_star(
            incident_id="abc-123",
            task="Resolve customer order tracking question",
            action="Asked manager for order #12345 status",
            result="Order shipped yesterday via courier"
        )
    """
    try:
        async with AsyncSessionLocal() as session:
            # Update incident with STAR components
            query = text("""
                UPDATE incidents
                SET task = :task, 
                    action = :action, 
                    result = CASE WHEN :result != '' THEN :result ELSE result END,
                    updated_at = NOW()
                WHERE id::text = :id
                RETURNING id::text
            """)
            
            result_row = await session.execute(query, {
                "id": incident_id,
                "task": task[:500],  # Truncate to prevent overflow
                "action": action[:1000],
                "result": result[:1000] if result else ""
            })
            
            updated_id = result_row.scalar_one_or_none()
            await session.commit()
            
            if not updated_id:
                logger.error(f"Failed to update incident {incident_id} - not found")
                return f"❌ Incident #{incident_id[:8]} not found"
            
            logger.info(f"Updated STAR for incident {incident_id}: task='{task[:50]}', action='{action[:50]}'")
            return f"✅ Incident #{incident_id[:8]} updated with action log"
            
    except Exception as e:
        logger.error(f"Failed to update incident STAR: {e}", exc_info=True)
        return f"❌ Error updating incident: {str(e)}"


@tool
async def relay_to_manager(
    user_id: str,
    incident_id: str,
    question: str,
    suggested_responses: Optional[List[str]] = None
) -> str:
    """
    Send question to manager and notify customer to expect response.
    
    Use for queries beyond support worker authority:
    - Order status ("Where is my order?")
    - Refund requests ("Can I get a refund?")
    - Custom exceptions
    
    Args:
        user_id: Customer phone number
        incident_id: Ticket ID for tracking
        question: Question to ask manager
        suggested_responses: Optional list of expected response formats
                            e.g., ["pending", "confirmed", "shipped", "delivered"]
        
    Returns:
        Message to send to customer
        
    Example:
        await relay_to_manager(
            user_id="2348012345678",
            incident_id="abc-123",
            question="What is the status of this customer's order?",
            suggested_responses=["pending", "confirmed", "shipped", "delivered"]
        )
    """
    try:
        # Validate manager contact configured
        if not settings.ADMIN_PHONE_NUMBERS or len(settings.ADMIN_PHONE_NUMBERS) == 0:
            logger.error("No admin phone numbers configured for manager relay")
            return (
                "I apologize, but I'm unable to reach the manager right now. "
                "Your ticket #{incident_id[:8]} has been created and we'll follow up soon! 🙏"
            )
        
        manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
        
        # Build response guide for manager
        response_guide = ""
        if suggested_responses:
            response_guide = f"\n\n📝 *Suggested responses:*\n{', '.join(suggested_responses)}"
        
        # Format manager message
        manager_message = (
            f"🆘 *SUPPORT QUERY*\n\n"
            f"📋 Ticket: #{incident_id[:8]}\n"
            f"👤 Customer: {user_id}\n"
            f"❓ Question: {question}\n"
            f"{response_guide}\n\n"
            f"Reply via WhatsApp or admin panel. Your response will be relayed to the customer."
        )
        
        # Send to manager via WhatsApp
        await meta_service.send_whatsapp_text(manager_phone, manager_message)
        
        logger.info(f"Relayed question to manager for incident {incident_id}: '{question[:50]}'")
        
        # Return customer-facing message
        return (
            f"I've contacted our team about your inquiry. "
            f"You'll receive an update shortly! 🙏\n\n"
            f"Your ticket number is *#{incident_id[:8]}* for reference."
        )
        
    except Exception as e:
        logger.error(f"Failed to relay to manager: {e}", exc_info=True)
        return (
            f"I've noted your concern (Ticket #{incident_id[:8]}). "
            f"Our team will reach out to you soon! 🙏"
        )


@tool
async def confirm_customer_resolution(
    incident_id: str,
    resolution_summary: str,
    customer_confirmed: bool = True
) -> str:
    """
    Mark incident as RESOLVED when customer confirms issue is fixed.
    
    ONLY use when ALL of these are true:
    1. Customer explicitly confirmed satisfaction ("Thanks!", "All good!", "Found it!")
    2. Issue was simple (tracking, status, general question)
    3. NO refund, replacement, or compensation involved
    
    DO NOT use for:
    - Refund requests (must stay ESCALATED until refund processes)
    - Damage/quality claims
    - Disputes or complaints
    - Anything requiring manager decision
    
    Args:
        incident_id: UUID of the incident
        resolution_summary: Brief description of how issue was resolved
        customer_confirmed: Must be True to proceed (safety check)
        
    Returns:
        Confirmation message
        
    Example:
        await confirm_customer_resolution(
            incident_id="abc-123",
            resolution_summary="Order status confirmed as shipped, customer satisfied",
            customer_confirmed=True
        )
    """
    try:
        # Safety check - require explicit confirmation
        if not customer_confirmed:
            logger.warning(f"Attempted to resolve incident {incident_id} without customer confirmation")
            return "❌ Cannot mark resolved - customer has not confirmed resolution"
        
        # Validate incident exists and is in valid state for resolution
        async with AsyncSessionLocal() as session:
            check_query = text("""
                SELECT status FROM incidents WHERE id::text = :id
            """)
            result = await session.execute(check_query, {"id": incident_id})
            row = result.fetchone()
            
            if not row:
                return f"❌ Incident #{incident_id[:8]} not found"
            
            current_status = row[0]
            
            # Don't allow resolution of escalated incidents (manager is handling)
            if current_status == "ESCALATED":
                logger.warning(f"Attempted to resolve ESCALATED incident {incident_id}")
                return (
                    f"⚠️ Incident #{incident_id[:8]} is with our manager. "
                    f"They will update you directly!"
                )
        
        # Mark as resolved
        async with AsyncSessionLocal() as session:
            resolve_query = text("""
                UPDATE incidents
                SET status = 'RESOLVED',
                    result = :resolution,
                    resolved_at = NOW()
                WHERE id::text = :id
                RETURNING id::text
            """)
            
            result = await session.execute(resolve_query, {
                "id": incident_id,
                "resolution": resolution_summary[:1000]
            })
            
            updated_id = result.scalar_one_or_none()
            await session.commit()
            
            if not updated_id:
                return f"❌ Failed to update incident {incident_id[:8]}"
        
        logger.info(f"Incident {incident_id} marked RESOLVED: {resolution_summary[:100]}")
        return f"✅ Ticket #{incident_id[:8]} has been marked as RESOLVED"
        
    except Exception as e:
        logger.error(f"Failed to confirm resolution: {e}", exc_info=True)
        return f"❌ Error marking incident resolved: {str(e)}"

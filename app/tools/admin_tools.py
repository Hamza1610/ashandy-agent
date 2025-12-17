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


@tool
async def get_top_customers(period: str = "week", limit: int = 10) -> str:
    """
    Get top customers by lead score for a period.
    Period: 'week', 'month', 'all'. Returns customers ranked by RFM score.
    Use this when admin asks "Who patronised us most?" or "Top customers".
    """
    try:
        from app.services.profile_service import profile_service
        from datetime import datetime, timedelta
        
        # Calculate date range
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(days=7)
            period_label = "This Week"
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_label = "This Month"
        else:
            start_date = now - timedelta(days=365)
            period_label = "All Time"
        
        async with AsyncSessionLocal() as session:
            # Get customers with orders in period
            query = text("""
                SELECT 
                    cp.user_id,
                    cp.total_purchases,
                    cp.total_spent,
                    cp.last_purchase_at,
                    cp.avg_sentiment
                FROM customer_profiles cp
                WHERE cp.last_purchase_at >= :start_date
                  AND cp.total_purchases > 0
                ORDER BY cp.total_spent DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"start_date": start_date, "limit": limit})
            rows = result.fetchall()
            
            if not rows:
                return f"📊 No customers with purchases in {period_label.lower()}."
            
            # Compute lead scores and format output
            output = f"📊 **Top Customers - {period_label}**\n\n"
            output += "| Rank | Customer | Orders | Spent | Score |\n"
            output += "|------|----------|--------|-------|-------|\n"
            
            for i, row in enumerate(rows, 1):
                r = dict(row._mapping)
                user_id = r.get('user_id', 'Unknown')
                # Mask user ID for privacy
                masked_id = f"...{user_id[-6:]}" if len(user_id) > 6 else user_id
                orders = r.get('total_purchases', 0)
                spent = r.get('total_spent', 0)
                
                # Compute lead score using profile service
                try:
                    score = await profile_service.compute_lead_score(user_id)
                except:
                    score = 50  # Default if computation fails
                
                output += f"| {i} | {masked_id} | {orders} | ₦{spent:,.0f} | {score}/100 |\n"
            
            return output
            
    except Exception as e:
        logger.error(f"Get top customers error: {e}")
        return f"Error retrieving customer data: {str(e)}"


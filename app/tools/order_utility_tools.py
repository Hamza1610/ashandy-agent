"""
Order Management Utility Tools: Admin tools for viewing and searching orders.
"""
from langchain_core.tools import tool
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@tool
async def get_recent_orders(limit: int = 10, hours: int = 24) -> str:
    """Get recent orders within specified time period.
    
    Useful for manager to check what orders came in recently.
    
    Args:
        limit: Maximum number of orders to show (default: 10)
        hours: Look back this many hours (default: 24)
        
    Returns:
        Formatted list of recent orders with key details
    """
    try:
        async with AsyncSessionLocal() as session:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            query = text("""
                SELECT 
                    id,
                    user_id,
                    amount,
                    payment_status,
                    delivery_details,
                    created_at
                FROM orders
                WHERE created_at >= :cutoff
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"cutoff": cutoff_time, "limit": limit})
            rows = result.fetchall()
            
            if not rows:
                return f"📭 No orders in the last {hours} hours."
            
            output = f"📦 **Recent Orders (Last {hours}h)** - {len(rows)} orders\\n\\n"
            
            for row in rows:
                r = dict(row._mapping)
                order_id = r.get('id', 'N/A')
                user_id = r.get('user_id', 'Unknown')
                masked_id = f"...{user_id[-10:]}" if len(user_id) > 10 else user_id
                amount = r.get('amount', 0)
                status = r.get('payment_status', 'unknown')
                created = r.get('created_at', 'N/A')
                
                status_emoji = {
                    'paid': '✅',
                    'pending': '⏳',
                    'manual_payment_pending': '💳',
                    'payment_rejected': '❌'
                }.get(status, '❓')
                
                output += f"""---
**Order #{order_id}** {status_emoji}
Customer: {masked_id}
Amount: ₦{amount:,.2f}
Status: {status}
Time: {created}

"""
            
            return output
            
    except Exception as e:
        logger.error(f"Error getting recent orders: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@tool
async def search_order_by_customer(customer_phone: str, limit: int = 5) -> str:
    """Find orders for a specific customer by phone number.
    
    Args:
        customer_phone: Customer's phone number (e.g., +2348012345678 or 08012345678)
        limit: Maximum number of orders to show (default: 5)
        
    Returns:
        Customer's order history with details
    """
    try:
        # Normalize phone number
        clean_phone = customer_phone.replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+"):
            # Assume Nigerian number
            if clean_phone.startswith("0"):
                clean_phone = "+234" + clean_phone[1:]
            elif clean_phone.startswith("234"):
                clean_phone = "+" + clean_phone
            else:
                clean_phone = "+234" + clean_phone
        
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT 
                    id,
                    amount,
                    payment_status,
                    delivery_details,
                    created_at,
                    verified_at
                FROM orders
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"user_id": clean_phone, "limit": limit})
            rows = result.fetchall()
            
            if not rows:
                return f"📭 No orders found for {clean_phone}"
            
            output = f"📋 **Order History for {clean_phone}** - {len(rows)} order(s)\\n\\n"
            
            total_spent = 0
            for row in rows:
                r = dict(row._mapping)
                order_id = r.get('id', 'N/A')
                amount = r.get('amount', 0)
                status = r.get('payment_status', 'unknown')
                created = r.get('created_at', 'N/A')
                verified = r.get('verified_at', None)
                
                if status == 'paid':
                    total_spent += amount
                
                status_emoji = {
                    'paid': '✅',
                    'pending': '⏳',
                    'manual_payment_pending': '💳',
                    'payment_rejected': '❌'
                }.get(status, '❓')
                
                output += f"""---
**Order #{order_id}** {status_emoji}
Amount: ₦{amount:,.2f}
Status: {status}
Created: {created}
{"Verified: " + str(verified) if verified else ""}

"""
            
            output += f"\\n💰 **Total Paid:** ₦{total_spent:,.2f}"
            
            return output
            
    except Exception as e:
        logger.error(f"Error searching orders: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@tool
async def view_order_details(order_id: int) -> str:
    """Get complete details of a specific order.
    
    Args:
        order_id: Order ID number
        
    Returns:
        Full order details including items, payment, delivery
    """
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT 
                    id,
                    user_id,
                    amount,
                    payment_status,
                    delivery_details,
                    created_at,
                    verified_at,
                    verification_notes,
                    reference
                FROM orders
                WHERE id = :order_id
            """)
            result = await session.execute(query, {"order_id": order_id})
            row = result.fetchone()
            
            if not row:
                return f"❌ Order #{order_id} not found"
            
            r = dict(row._mapping)
            user_id = r.get('user_id', 'Unknown')
            masked_id = f"...{user_id[-10:]}" if len(user_id) > 10 else user_id
            amount = r.get('amount', 0)
            status = r.get('payment_status', 'unknown')
            delivery_details = r.get('delivery_details', {})
            created = r.get('created_at', 'N/A')
            verified = r.get('verified_at', None)
            notes = r.get('verification_notes', 'None')
            reference = r.get('reference', 'N/A')
            
            status_emoji = {
                'paid': '✅',
                'pending': '⏳',
                'manual_payment_pending': '💳',
                'payment_rejected': '❌'
            }.get(status, '❓')
            
            # Parse delivery details
            if isinstance(delivery_details, str):
                import json
                try:
                    delivery_details = json.loads(delivery_details)
                except:
                    delivery_details = {}
            
            delivery_info = ""
            if delivery_details:
                delivery_info = f"""
**Delivery Details:**
Name: {delivery_details.get('name', 'N/A')}
Phone: {delivery_details.get('phone', 'N/A')}
Address: {delivery_details.get('address', 'N/A')}
City: {delivery_details.get('city', 'N/A')}
"""
            
            output = f"""📦 **Order #{order_id}** {status_emoji}

**Customer:** {masked_id}
**Reference:** {reference}
**Amount:** ₦{amount:,.2f}
**Status:** {status}

**Timeline:**
Created: {created}
{f"Verified: {verified}" if verified else "Not yet verified"}

{delivery_info}

**Notes:** {notes}

---
To view items, check order in POS system.
"""
            
            return output
            
    except Exception as e:
        logger.error(f"Error viewing order details: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"

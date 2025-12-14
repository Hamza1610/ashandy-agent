"""
Approval Tools: High-value order approval workflow via WhatsApp.

Uses atomic Redis hash operations to prevent race conditions when
multiple workers access the approval waitlist concurrently.
"""
from langchain.tools import tool
from app.services.meta_service import meta_service
from app.utils.config import settings
from app.services.cache_service import cache_service
import logging
import json

logger = logging.getLogger(__name__)

WAITLIST_KEY = "approval_waitlist"


async def get_waitlist() -> dict:
    """
    Retrieves pending orders from Redis using atomic HGETALL.
    Returns dict of {user_id: order_data}.
    """
    raw_dict = await cache_service.hgetall(WAITLIST_KEY)
    return {k: json.loads(v) for k, v in raw_dict.items()} if raw_dict else {}


async def add_to_waitlist(user_id: str, amount: float, items: str):
    """
    Atomically adds an order to the waitlist using HSET.
    Prevents race conditions where concurrent adds would lose data.
    """
    order_data = json.dumps({"amount": amount, "items": items, "timestamp": "now"})
    await cache_service.hset(WAITLIST_KEY, user_id, order_data)
    logger.info(f"Added {user_id} to approval waitlist (atomic)")


async def remove_from_waitlist(user_id: str):
    """
    Atomically removes an order from the waitlist using HDEL.
    """
    await cache_service.hdel(WAITLIST_KEY, user_id)
    logger.info(f"Removed {user_id} from approval waitlist (atomic)")


@tool
async def request_order_approval(user_id: str, amount: float, items_summary: str):
    """Send approval request to manager and add to waitlist."""
    if not settings.ADMIN_PHONE_NUMBERS:
        return "No admin configured."
        
    await add_to_waitlist(user_id, amount, items_summary)
    
    msg = f"🚨 *HIGH VALUE ORDER*\n👤 {user_id}\n💰 ₦{amount:,.2f}\n📦 {items_summary}\n----\nReply *'Approve'* or *'Reject'*"
    await meta_service.send_whatsapp_text(settings.ADMIN_PHONE_NUMBERS[0], msg)
    return "Approval request sent."


@tool
async def list_pending_approvals():
    """Returns formatted list of pending orders."""
    waitlist = await get_waitlist()
    if not waitlist:
        return "No pending approvals."
    text = "📋 *PENDING APPROVALS:*\n"
    for i, (uid, data) in enumerate(waitlist.items(), 1):
        text += f"{i}. {uid} - ₦{data['amount']:,.2f} ({data['items']})\n"
    return text


@tool
async def approve_order(target_user_id: str = None):
    """Approve an order. Auto-resolves if only one pending."""
    waitlist = await get_waitlist()
    
    if not target_user_id:
        if len(waitlist) == 1:
            target_user_id = list(waitlist.keys())[0]
        elif len(waitlist) > 1:
            return f"⚠️ Ambiguous: {len(waitlist)} pending. Specify which user.\n" + await list_pending_approvals()
        else:
            return "No pending orders."

    if target_user_id not in waitlist:
        return f"Error: {target_user_id} not on waitlist."
        
    await remove_from_waitlist(target_user_id)
    await meta_service.send_whatsapp_text(target_user_id, "✅ *Order Approved!*\nPlease proceed with payment.")
    return f"✅ Approved {target_user_id}."


@tool
async def reject_order(target_user_id: str = None, reason: str = "Manager declined"):
    """Reject an order with a reason."""
    waitlist = await get_waitlist()
    
    if not target_user_id:
        if len(waitlist) == 1:
            target_user_id = list(waitlist.keys())[0]
        elif len(waitlist) > 1:
            return f"⚠️ Which user to reject?\n" + await list_pending_approvals()
        else:
            return "No pending orders."

    if target_user_id not in waitlist:
        return f"Error: {target_user_id} not found."
        
    await remove_from_waitlist(target_user_id)
    await meta_service.send_whatsapp_text(target_user_id, f"⚠️ *Order Update*\n{reason}\nContact us to adjust.")
    return f"🚫 Rejected {target_user_id}. Reason: {reason}"

from langchain.tools import tool
from app.services.meta_service import meta_service
from app.utils.config import settings
from app.services.cache_service import cache_service
import logging
import json

logger = logging.getLogger(__name__)

# --- WAITLIST HELPERS ---

async def get_waitlist() -> dict:
    """Retrieves the list of pending orders from Redis."""
    raw = await cache_service.get("approval_waitlist")
    if not raw:
        return {}
    return json.loads(raw)

async def add_to_waitlist(user_id: str, amount: float, items: str):
    """Adds an order to the waitlist."""
    waitlist = await get_waitlist()
    waitlist[user_id] = {"amount": amount, "items": items, "timestamp": "now"} # Simplified
    await cache_service.set("approval_waitlist", json.dumps(waitlist), expire=86400)

async def remove_from_waitlist(user_id: str):
    """Removes an order from the waitlist."""
    waitlist = await get_waitlist()
    if user_id in waitlist:
        del waitlist[user_id]
        await cache_service.set("approval_waitlist", json.dumps(waitlist), expire=86400)

# --- TOOLS ---

@tool
async def request_order_approval(user_id: str, amount: float, items_summary: str):
    """
    Sends approval request. Adds to Waitlist.
    """
    if not settings.ADMIN_PHONE_NUMBERS:
        return "No admin configured."
        
    manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
    
    # Add to Multi-Order Waitlist
    await add_to_waitlist(user_id, amount, items_summary)
    
    msg = (
        f"🚨 *HIGH VALUE ORDER WAITLIST*\n"
        f"👤 Customer: {user_id}\n"
        f"💰 Amount: ₦{amount:,.2f}\n"
        f"📦 Items: {items_summary}\n"
        f"-----------------------------\n"
        f"Reply *'Approve'* or *'Reject'* (or ask questions)."
    )
    
    await meta_service.send_whatsapp_text(manager_phone, msg)
    return "Approval request sent."

@tool
async def list_pending_approvals():
    """Returns a formatted list of all pending orders for the Manager."""
    waitlist = await get_waitlist()
    if not waitlist:
        return "No pending approvals."
        
    text = "📋 *PENDING APPROVALS:*\n"
    for i, (uid, data) in enumerate(waitlist.items(), 1):
        text += f"{i}. {uid} - ₦{data['amount']:,.2f} ({data['items']})\n"
    
    return text

@tool
async def approve_order(target_user_id: str = None):
    """
    Approves an order. 
    If target_user_id is None, it checks if there is EXACTLY ONE pending order.
    If multiple, it asks for clarification.
    """
    waitlist = await get_waitlist()
    
    # 1. Auto-Resolve Context
    if not target_user_id:
        if len(waitlist) == 1:
            target_user_id = list(waitlist.keys())[0]
        elif len(waitlist) > 1:
            return f"⚠️ **Ambiguous:** There are {len(waitlist)} pending orders. Please specify which user (e.g. 'Approve the first one' or 'Approve +234...').\n" + await list_pending_approvals()
        else:
            return "No pending orders to approve."

    # 2. Process
    if target_user_id not in waitlist:
        return f"Error: User {target_user_id} is not on the waitlist."
        
    await remove_from_waitlist(target_user_id)

    # Notify User
    msg = (
        f"✅ *Order Approved!*\n"
        f"Our manager has reviewed your order.\n"
        f"Please proceed with payment."
    )
    await meta_service.send_whatsapp_text(target_user_id, msg)
    return f"✅ Approved User {target_user_id}."

@tool
async def reject_order(target_user_id: str = None, reason: str = "Manager declined"):
    """
    Rejects an order and notifies the user with a reason.
    Handles 'Out of Stock' or other manager feedback.
    """
    waitlist = await get_waitlist()
    
    # 1. Auto-Resolve Context
    if not target_user_id:
        if len(waitlist) == 1:
            target_user_id = list(waitlist.keys())[0]
        elif len(waitlist) > 1:
            return f"⚠️ **Ambiguous:** Which user are you rejecting? Pending:\n" + await list_pending_approvals()
        else:
            return "No pending orders to reject."

    if target_user_id not in waitlist:
        return f"Error: User {target_user_id} not found."
        
    await remove_from_waitlist(target_user_id)
    
    # Notify User
    msg = (
        f"⚠️ *Order Update*\n"
        f"Manager Message: {reason}\n"
        f"Please contact us if you'd like to adjust your order."
    )
    await meta_service.send_whatsapp_text(target_user_id, msg)
    return f"🚫 Rejected User {target_user_id}. Reason: {reason}"

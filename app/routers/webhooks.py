"""
Webhooks Router: Handles incoming messages from WhatsApp, Instagram, and Paystack.
"""
from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.utils.config import settings
from app.models.webhook_schemas import WhatsAppWebhookPayload, InstagramWebhookPayload
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limiter for webhooks (60 messages/minute per IP)
limiter = Limiter(key_func=get_remote_address)


@router.get("/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """Verification challenge for Meta WhatsApp Cloud API."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        logger.info("WhatsApp Webhook Verified!")
        return int(challenge)
    elif mode and token:
        raise HTTPException(status_code=403, detail="Verification failed")
    return {"status": "ok"}


@router.post("/whatsapp")
@limiter.limit("60/minute")
async def receive_whatsapp_webhook(request: Request, payload: WhatsAppWebhookPayload):
    """Process incoming WhatsApp messages."""
    from app.graphs.main_graph import app as agent_app
    from langchain_core.messages import HumanMessage
    from app.services.meta_service import meta_service

    try:
        if not payload.entry or not payload.entry[0].changes:
            return {"status": "no_entry"}

        entry = payload.entry[0]
        if not entry.changes:
            return {"status": "no_changes"}

        changes = entry.changes[0]
        value = changes.value
        
        if not value:
             return {"status": "no_value"}
             
        messages = value.messages
        if not messages:
            return {"status": "no_messages"}

        message = messages[0]
        from_phone = message.from_ # The user's phone number
        
        # Extract message content
        content = ""
        msg_type = message.type
        
        user_message_content = ""
        image_url = None
        
        if msg_type == "text":
            text_obj = message.text
            user_message_content = text_obj.body if text_obj else ""
        elif msg_type == "image":
            # Handle Image
            img_obj = message.image
            media_id = img_obj.id if img_obj else None
            caption = img_obj.caption if img_obj else ""
            user_message_content = caption or "" # Use caption as text context
            
            # Resolve URL
            fetched_url = await meta_service.get_media_url(media_id)
            if fetched_url:
                image_url = fetched_url
            else:
                logger.warning(f"Could not resolve URL for media {media_id}")
        else:
            logger.warning(f"⚠️ Cannot extract message. Type: {msg_type}, Has text: {hasattr(message, 'text')}, Has image: {hasattr(message, 'image')}")
            
        logger.info(f"📝 Final user_message_content: '{user_message_content}' (length: {len(user_message_content)})")
            
        # Construct Input State
        # We need to pass the image URL in a way the Router understands.
        # Router checks: additional_kwargs["image_url"] 
        
        msg_kwargs = {}
        if image_url:
            msg_kwargs["image_url"] = image_url
            # Also constructing multimodal content block for LangChain purity
            # content = [{"type": "text", "text": user_message_content}, {"type": "image_url", "image_url": {"url": image_url}}]
        
        logger.info(f"Webhook: Creating HumanMessage with content: '{user_message_content[:100] if user_message_content else 'EMPTY'}'")
        
        human_msg = HumanMessage(content=user_message_content)
        if image_url:
            human_msg.additional_kwargs["image_url"] = image_url
        
        input_state = {
            "messages": [human_msg],
            "user_id": from_phone,
            "session_id": from_phone,
            "platform": "whatsapp",
            "is_admin": False,
            "blocked": False,
            "order_intent": False,
            "requires_handoff": False,
            "query_type": "text",
            "last_user_message": user_message_content
        }
        
        final_state = await agent_app.ainvoke(input_state, config={"configurable": {"thread_id": from_phone}})
        
        final_messages = final_state.get("messages", [])
        last_reply = None
        
        for msg in reversed(final_messages):
            msg_type = type(msg).__name__
            if msg_type in ["HumanMessage", "ToolMessage"]:
                continue
            if hasattr(msg, 'content') and msg.content and isinstance(msg.content, str):
                last_reply = msg.content.strip()
                break

        # Save memory
        if user_message_content and last_reply:
            try:
                from app.tools.vector_tools import save_user_interaction
                await save_user_interaction(user_id=from_phone, user_msg=user_message_content, ai_msg=last_reply)
            except Exception as e:
                logger.error(f"Memory save error: {e}")
        
        return {"status": "processed", "channel": "whatsapp", "user_id": from_phone, "last_reply": last_reply}
            
    except Exception as e:
        logger.error(f"WhatsApp processing error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/instagram")
async def verify_instagram_webhook(request: Request):
    """Verification challenge for Instagram Graph API."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return int(challenge)
    elif mode and token:
        raise HTTPException(status_code=403, detail="Verification failed")
    return {"status": "ok"}


@router.post("/instagram")
async def receive_instagram_webhook(payload: InstagramWebhookPayload):
    """Process incoming Instagram messages."""
    from app.graphs.main_graph import app as graph_app
    from langchain_core.messages import HumanMessage
    from app.services.meta_service import meta_service

    try:
        if not payload.entry or not payload.entry[0].messaging:
            return {"status": "no_entry"}
            
        event = payload.entry[0].messaging[0]
        sender_id = event.sender["id"]
        
        if not event.message:
            return {"status": "ignored_non_message"}
              
        text_content = event.message.text or ""
        
        image_url = None
        if event.message.attachments:
            for att in event.message.attachments:
                if att.get("type") == "image":
                    image_url = att.get("payload", {}).get("url")
                    break
        
        human_msg = HumanMessage(content=text_content)
        if image_url:
            human_msg.additional_kwargs["image_url"] = image_url
        
        input_state = {
            "messages": [human_msg],
            "user_id": sender_id,
            "session_id": sender_id,
            "platform": "instagram",
            "is_admin": False,
            "blocked": False,
            "order_intent": False,
            "requires_handoff": False,
            "query_type": "text",
            "last_user_message": text_content
        }
        
        final_state = await graph_app.ainvoke(input_state, config={"configurable": {"thread_id": sender_id}})
        
        final_messages = final_state.get("messages", [])
        last_reply = final_messages[-1].content if final_messages else None
        
        if text_content and last_reply:
            try:
                from app.tools.vector_tools import save_user_interaction
                await save_user_interaction(user_id=sender_id, user_msg=text_content, ai_msg=last_reply)
            except Exception as e:
                logger.error(f"Instagram memory error: {e}")
        
        return {"status": "processed", "channel": "instagram", "user_id": sender_id, "last_reply": last_reply}

    except Exception as e:
        logger.error(f"IG Webhook error: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/paystack")
async def receive_paystack_webhook(request: Request):
    """Handle Paystack payment webhooks."""
    from app.services.meta_service import meta_service
    from app.tools.db_tools import get_order_by_reference

    try:
        payload = await request.json()
        event = payload.get("event")
        data = payload.get("data", {})
        
        if event == "charge.success":
            reference = data.get("reference")
            amount_naira = data.get("amount", 0) / 100
            customer_email = data.get("customer", {}).get("email", "N/A")
            
            if settings.ADMIN_PHONE_NUMBERS:
                manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
                
                try:
                    order = await get_order_by_reference.ainvoke(reference)
                except Exception:
                    order = {}

                if not isinstance(order, dict):
                    order = {}
                
                details = order.get("details", {})
                items = details.get("items", [])
                delivery_info = details.get("delivery_details", {})
                
                items_str = "".join([f"- {i.get('name', 'Item')} (x{i.get('quantity', 1)}): ₦{i.get('price', 0):,.2f}\n" for i in items])
                addr_str = f"{delivery_info.get('address', '')}, {delivery_info.get('city', '')}" if isinstance(delivery_info, dict) else str(delivery_info)

                msg = (
                    f"✅ *PAYMENT CONFIRMED*\n"
                    f"🧾 *Ref:* {reference}\n"
                    f"------------------------------\n"
                    f"*Items:*\n{items_str}"
                    f"------------------------------\n"
                    f"🛍️ *Subtotal:* ₦{details.get('subtotal', 0):,.2f}\n"
                    f"🚚 *Delivery Fee:* ₦{details.get('delivery_fee', 0):,.2f}\n"
                    f"💰 *TOTAL PAID:* ₦{amount_naira:,.2f}\n"
                    f"------------------------------\n"
                    f"📦 *Delivery To:* {addr_str}\n"
                    f"📞 *Phone:* {order.get('user_id', 'N/A')}\n"
                    f"📧 *Email:* {customer_email}"
                )
                
                await meta_service.send_whatsapp_text(manager_phone, msg)
                logger.info(f"Admin notified of payment: {reference}")
                
            # Update local DB status to PAID (Source of Truth)
            from app.services.db_service import AsyncSessionLocal
            from sqlalchemy import text
            
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE orders SET status = 'PAID' WHERE paystack_reference = :ref"),
                    {"ref": reference}
                )
                await session.commit()
                logger.info(f"Order {reference} marked as PAID in DB.")
                
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Paystack Webhook Error: {e}")
        return {"status": "error"}

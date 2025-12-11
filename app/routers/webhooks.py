from fastapi import APIRouter, Request, HTTPException, status
from app.utils.config import settings
from app.models.webhook_schemas import WhatsAppWebhookPayload, InstagramWebhookPayload
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# WhatsApp Webhook
@router.get("/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """
    Verification challenge for Meta WhatsApp Cloud API.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
            logger.info("WhatsApp Webhook Verified!")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    
    return {"status": "ok"}

@router.post("/whatsapp")
async def receive_whatsapp_webhook(payload: WhatsAppWebhookPayload):
    """
    Receive WhatsApp messages.
    """
    from app.workflows.main_workflow import app as agent_app
    from langchain_core.messages import HumanMessage
    from app.services.meta_service import meta_service

    # payload is already parsed by Pydantic
    logger.info(f"Received WhatsApp webhook.")
    
    try:
        # Access attributes directly, respecting Pydantic model structure
        if not payload.entry:
            return {"status": "no_entry"}

        entry = payload.entry[0]
        if not entry.changes:
            return {"status": "no_changes"}

        changes = entry.changes[0]
        value = changes.value
        messages = value.messages

        if not messages:
            return {"status": "no_messages"}

        message = messages[0]
        from_phone = message.get("from") # The user's phone number
        
        # Extract message content
        content = ""
        msg_type = message.type
        
        user_message_content = ""
        image_url = None
        if msg_type == "text":
            text_obj = message.get("text", {})
            user_message_content = text_obj.get("body", "")
        elif msg_type == "image":
            # Handle Image
            img_obj = message.get("image", {})
            media_id = img_obj.get("id")
            caption = img_obj.get("caption", "")
            user_message_content = caption # Use caption as text context
            
            # Resolve URL
            fetched_url = await meta_service.get_media_url(media_id)
            if fetched_url:
                image_url = fetched_url
            else:
                logger.warning(f"Could not resolve URL for media {media_id}")
            
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
        
        logger.info(f"Webhook: HumanMessage created. Content type: {type(human_msg.content).__name__}, Content: '{str(human_msg.content)[:100] if human_msg.content else 'EMPTY'}'")
        
        input_state = {
            "messages": [human_msg],
            "user_id": from_phone,
            "session_id": from_phone,
            "platform": "whatsapp",
            "is_admin": False
        }
        
        # Invoke Graph
        logger.info(f"Invoking Agent Graph for {from_phone}...")
        final_state = await agent_app.ainvoke(input_state, config={"configurable": {"thread_id": from_phone}})
        
        send_result = final_state.get("send_result")
        final_messages = final_state.get("messages", [])
        last_reply = final_messages[-1].content if final_messages else None
        
        return {
            "status": "processed",
            "channel": "whatsapp",
            "user_id": from_phone,
            "send_result": send_result,
            "last_reply": last_reply
        }
            
    except Exception as e:
        logger.error(f"WhatsApp processing error: {e}")
        return {"status": "error", "message": str(e)}

# Instagram Webhook
@router.get("/instagram")
async def verify_instagram_webhook(request: Request):
    """
    Verification challenge for Instagram Graph API.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.META_VERIFY_TOKEN: # Assuming same verify token
             return int(challenge)
        else:
             raise HTTPException(status_code=403, detail="Verification failed")
    
    return {"status": "ok"}

@router.post("/instagram")
async def receive_instagram_webhook(payload: InstagramWebhookPayload):
    from app.workflows.main_workflow import app as graph_app
    from langchain_core.messages import HumanMessage
    from app.services.meta_service import meta_service

    try:
        # logger.info(f"Received Instagram webhook: {payload}")
        
        if not payload.entry:
             return {"status": "no_entry"}
             
        entry = payload.entry[0]
        if not entry.messaging:
             return {"status": "ignored_event_type"}
            
        event = entry.messaging[0]
        sender_id = event.sender["id"]
        
        if not event.message:
             return {"status": "ignored_non_message"}
             
        message = event.message
        text_content = message.text or ""
        
        # Check for attachments (images)
        image_url = None
        if message.attachments:
            for att in message.attachments:
                if att.get("type") == "image":
                    # IG Attachments usually provide a payload.url directly
                    payload_url = att.get("payload", {}).get("url")
                    if payload_url:
                        image_url = payload_url
                        break
        
        # Construct Message
        human_msg = HumanMessage(content=text_content)
        if image_url:
             human_msg.additional_kwargs["image_url"] = image_url
        
        # Construct Input State
        input_state = {
            "messages": [human_msg],
            "user_id": sender_id,
            "session_id": sender_id,
            "platform": "instagram",
            "is_admin": False
        }
        
        # Invoke Graph
        logger.info(f"Invoking Agent Graph for IG User {sender_id}...")
        final_state = await graph_app.ainvoke(input_state, config={"configurable": {"thread_id": sender_id}})
        
        send_result = final_state.get("send_result")
        final_messages = final_state.get("messages", [])
        last_reply = final_messages[-1].content if final_messages else None
        
        return {
            "status": "processed",
            "channel": "instagram",
            "user_id": sender_id,
            "send_result": send_result,
            "last_reply": last_reply
        }

    except Exception as e:
        logger.error(f"IG Webhook processing error: {e}")
        return {"status": "error", "message": str(e)}

# Paystack Webhook
@router.post("/paystack")
async def receive_paystack_webhook(request: Request):
    """
    Handle Paystack Webhooks (e.g., charge.success).
    """
    from app.services.meta_service import meta_service
    from app.utils.config import settings
    from app.tools.db_tools import get_order_by_reference

    try:
        payload = await request.json()
        event = payload.get("event")
        data = payload.get("data", {})
        
        logger.info(f"Paystack Webhook Event: {event}")
        
        if event == "charge.success":
            reference = data.get("reference")
            amount_kobo = data.get("amount", 0)
            amount_naira = amount_kobo / 100
            customer_email = data.get("customer", {}).get("email", "N/A")
            
            # Notify Admin
            if settings.ADMIN_PHONE_NUMBERS:
                manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
                
                # Fetch full details from DB
                try:
                    # Using tool invocation
                    order = await get_order_by_reference.ainvoke(reference)
                except Exception as db_e:
                    logger.error(f"Failed to fetch order: {db_e}")
                    order = {}

                if not isinstance(order, dict):
                     # Fallback if tool returns string error
                     order = {}
                
                details = order.get("details", {})
                items = details.get("items", [])
                subtotal = details.get("subtotal", 0)
                fee = details.get("delivery_fee", 0)
                delivery_info = details.get("delivery_details", {})
                
                # Build Invoice
                items_str = ""
                for item in items:
                    i_name = item.get("name", "Item")
                    i_qty = item.get("quantity", 1)
                    i_price = item.get("price", 0)
                    items_str += f"- {i_name} (x{i_qty}): ₦{i_price:,.2f}\n"
                
                if isinstance(delivery_info, dict):
                     addr_str = f"{delivery_info.get('address', '')}, {delivery_info.get('city', '')}"
                else:
                     addr_str = str(delivery_info)

                msg = (
                    f"✅ *PAYMENT CONFIRMED*\n"
                    f"🧾 *Ref:* {reference}\n"
                    f"------------------------------\n"
                    f"*Items:*\n{items_str}"
                    f"------------------------------\n"
                    f"🛍️ *Subtotal:* ₦{subtotal:,.2f}\n"
                    f"🚚 *Delivery Fee:* ₦{fee:,.2f}\n"
                    f"💰 *TOTAL PAID:* ₦{amount_naira:,.2f}\n"
                    f"------------------------------\n"
                    f"📦 *Delivery To:* {addr_str}\n"
                    f"📧 *Cust Email:* {customer_email}"
                )
                
                await meta_service.send_whatsapp_text(manager_phone, msg)
                logger.info(f"Admin notified of payment: {reference}")
                
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Paystack Webhook Error: {e}")
        return {"status": "error"}

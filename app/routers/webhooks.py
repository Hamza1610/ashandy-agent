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
    Receive WhatsApp messages (Typed Schema).
    """
    from app.workflows.main_workflow import app as graph_app
    from langchain_core.messages import HumanMessage
    from app.services.meta_service import meta_service
    from app.models.agent_states import AgentState

    try:
        # Pydantic parsing happens automatically now.
        # Access data via object attributes
        if not payload.entry:
             return {"status": "no_entry"}
             
        entry = payload.entry[0]
        if not entry.changes:
             return {"status": "no_changes"}
             
        change = entry.changes[0]
        if not change.value.messages:
             return {"status": "ignored_status_update"}
             
        message = change.value.messages[0]
        from_phone = message.from_
        msg_type = message.type
        
        user_message_content = ""
        image_url = None
        
        if msg_type == "text" and message.text:
            user_message_content = message.text.body
        elif msg_type == "image" and message.image:
            # Handle Image
            media_id = message.image.id
            caption = message.image.caption or ""
            user_message_content = caption # Use caption as text context
            
            # Resolve URL
            # Note: This URL is authenticated. The Visual Tool needs to handle it.
            # Ideally we pass headers or download here. 
            # For checking flows, we pass the URL. 
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
        
        human_msg = HumanMessage(content=user_message_content)
        if image_url:
             human_msg.additional_kwargs["image_url"] = image_url
        
        input_state = {
            "messages": [human_msg],
            "user_id": from_phone,
            "session_id": from_phone,
            "platform": "whatsapp",
            "is_admin": False
        }
        
        # Invoke Graph
        logger.info(f"Invoking Agent Graph for {from_phone}...")
        final_state = await graph_app.ainvoke(input_state, config={"configurable": {"thread_id": from_phone}})
        
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
        logger.error(f"Webhook processing error: {e}")
        # Return 200 to prevent Meta retries on logic errors
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
    # Verify signature
    # Process payment success
    return {"status": "received"}

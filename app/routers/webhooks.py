from fastapi import APIRouter, Request, HTTPException, status
from app.utils.config import settings
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
async def receive_whatsapp_webhook(request: Request):
    """
    Receive WhatsApp messages.
    """
    try:
        payload = await request.json()
        logger.info(f"Received WhatsApp webhook: {payload}")
    except Exception as e:
        logger.warning(f"Failed to decode JSON payload: {e}")
        return {"status": "error", "message": "Invalid JSON body"}
    
    # Imports for graph execution
    from app.workflows.main_workflow import app as graph_app
    from langchain_core.messages import HumanMessage
    from app.services.meta_service import meta_service

    # Basic parsing logic for WhatsApp Cloud API
    # Structure: entry[0].changes[0].value.messages[0]
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            # Maybe a status update
            return {"status": "ignored_status_update"}
            
        message = messages[0]
        from_phone = message.get("from") # User ID
        msg_type = message.get("type")
        
        user_message_content = ""
        image_url = None
        
        if msg_type == "text":
            user_message_content = message.get("text", {}).get("body", "")
        elif msg_type == "image":
            # For this MVP, we might not have full media download logic here w/o tokens.
            # But let's assume we get an ID or URL if accessible.
            # Actual Meta API requires retrieval via ID. 
            # We will use caption if available or placeholder.
            user_message_content = message.get("image", {}).get("caption", "")
            # Logic to get URL would go here. For now, we skip heavy media logic 
            # or assume a public URL if provided (unlikely in standard API).
            # To fix: We need a media_id -> URL helper.
            pass
            
        # Construct Input State
        input_state = {
            "messages": [HumanMessage(content=user_message_content)],
            "user_id": from_phone,
            "platform": "whatsapp",
            "is_admin": False # Router will check this
        }
        
        # Invoke Graph
        logger.info(f"Invoking Agent Graph for {from_phone}...")
        final_state = await graph_app.ainvoke(input_state)
        
        # Extract Response
        # We assume the last message in state['messages'] is the AI response (SystemMessage or AI Message)
        final_messages = final_state.get("messages", [])
        if final_messages:
            last_msg = final_messages[-1]
            response_text = last_msg.content
            
            # Send back via Meta/Twilio
            await meta_service.send_whatsapp_text(from_phone, response_text)
            logger.info("Response sent to user.")
            
        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
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
async def receive_instagram_webhook(request: Request):
    try:
        payload = await request.json()
        logger.info(f"Received Instagram webhook: {payload}")
    except Exception as e:
        logger.warning(f"Failed to decode JSON payload: {e}")
        return {"status": "error", "message": "Invalid JSON body"}
        
    return {"status": "received"}

# Paystack Webhook
@router.post("/paystack")
async def receive_paystack_webhook(request: Request):
    # Verify signature
    # Process payment success
    return {"status": "received"}

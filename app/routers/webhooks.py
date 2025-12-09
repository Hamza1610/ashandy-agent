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
    from app.workflows.main_workflow import app as agent_app
    from langchain_core.messages import HumanMessage

    payload = await request.json()
    logger.info(f"Received WhatsApp webhook: {payload}")
    
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no_messages"}

        message = messages[0]
        wa_id = message.get("from") # The user's phone number
        
        # Extract message content
        content = ""
        msg_type = message.get("type")
        
        if msg_type == "text":
            content = message["text"]["body"]
        elif msg_type == "image":
            # For now just handle as text or pass image URL if we had it
            # Ideally we extract the image ID and get the URL
            content = "User sent an image" 
            # Note: handling actual image retrieval requires Meta API call with media ID
            # For this MVP step we focus on text/admin commands

        if wa_id and content:
            # Inputs for the flow
            inputs = {
                "messages": [HumanMessage(content=content)],
                "user_id": wa_id,
                "platform": "whatsapp",
                "is_admin": False # Router will decide
            }
            
            # Run the graph
            # Use ainvoke for async execution
            await agent_app.ainvoke(inputs)
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
            
    return {"status": "processed"}

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
    payload = await request.json()
    logger.info(f"Received Instagram webhook: {payload}")
    return {"status": "received"}

# Paystack Webhook
@router.post("/paystack")
async def receive_paystack_webhook(request: Request):
    # Verify signature
    # Process payment success
    return {"status": "received"}

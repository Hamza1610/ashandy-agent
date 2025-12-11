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
    print("\n" + "="*100)
    print(">>> WEBHOOK FUNCTION CALLED - NEW CODE VERSION <<<")
    print("="*100 + "\n")
    
    from app.graphs.main_graph import app as agent_app
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
        wa_id = message.from_ # 'from' is aliased to 'from_' in schema
        from_phone = wa_id # Ensure we have this variable for later use
        
        # Extract message content
        content = ""
        msg_type = message.type
        
        user_message_content = ""
        image_url = None

        logger.info(f"📥 Webhook: message type='{msg_type}'")
        
        # Handle text messages - check for text attribute even if type is None
        if hasattr(message, 'text') and message.text:
            try:
                user_message_content = message.text.body
                logger.info(f"✅ Extracted text: '{user_message_content}'")
            except AttributeError:
                # Fallback if text.body doesn't exist
                user_message_content = str(message.text)
                logger.info(f"✅ Extracted text (fallback): '{user_message_content}'")
        elif msg_type == "image" and hasattr(message, 'image') and message.image:
            # Handle Image
            media_id = message.image.id
            caption = message.image.caption or ""
            user_message_content = caption
            logger.info(f"📸 Image message. Caption: '{caption}'")
            
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
        
        logger.info(f"Webhook: HumanMessage created. Content type: {type(human_msg.content).__name__}, Content: '{str(human_msg.content)[:100] if human_msg.content else 'EMPTY'}'")
        
        # Construct Input State with ALL required fields
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
        
        # Invoke Graph
        print("\n>>> ABOUT TO INVOKE GRAPH <<<")
        print(f">>> User: {from_phone}")
        print(f">>> Input state keys: {list(input_state.keys())}")
        
        final_state = await agent_app.ainvoke(input_state, config={"configurable": {"thread_id": from_phone}})
        
        print("\n>>> GRAPH COMPLETED <<<")
        print(f">>> Final state keys: {list(final_state.keys())}")
        
        send_result = final_state.get("send_result")
        final_messages = final_state.get("messages", [])
        
        print(f"\n>>> Messages in final_state: {len(final_messages)}")
        for i, msg in enumerate(final_messages):
            msg_type = type(msg).__name__
            has_content = hasattr(msg, 'content')
            content_preview = str(msg.content)[:50] if (has_content and msg.content) else "EMPTY"
            print(f">>>   [{i}] {msg_type} - {content_preview}")
        
        # Extract AI response - look for last AIMessage with actual text content
        last_reply = None
        
        # Search backwards through messages for last AI response with content
        for msg in reversed(final_messages):
            msg_type = type(msg).__name__
            logger.info(f"🔍 Checking message type={msg_type}")
            
            # Skip HumanMessage
            if msg_type == "HumanMessage":
                logger.info(f"   Skipping HumanMessage")
                continue
                
            # Skip ToolMessage (these are tool results, not final responses)
            if msg_type == "ToolMessage":
                logger.info(f"   Skipping ToolMessage")
                continue
            
            # Try to get content from this message
            content = None
            if hasattr(msg, 'content') and msg.content:
                content = msg.content
                logger.info(f"   Has content attribute: '{str(content)[:50]}'")
            elif isinstance(msg, dict) and msg.get('content'):
                content = msg['content']
                logger.info(f"   Dict with content: '{content[:50]}'")
            elif isinstance(msg, str):
                content = msg
                logger.info(f"   Is string: '{content[:50]}'")
            else:
                logger.info(f"   No content found")
                
            # If we found content, use it
            if content and isinstance(content, str) and content.strip():
                last_reply = content.strip()
                logger.info(f"✅ Found AI response: '{last_reply[:100]}'")
                break
            else:
                logger.info(f"   Message has no text content (might have tool_calls)")
        
        if not last_reply:
            logger.warning(f"⚠️ No AI text response found in {len(final_messages)} messages")
        
        logger.info(f"📤 Final AI Response: '{last_reply[:100] if last_reply else 'NONE'}'")
        
        # 🔥 FALLBACK: Save memory directly in webhook
        try:
            if user_message_content and last_reply:
                from app.tools.vector_tools import save_user_interaction
                logger.info(f"💾 Webhook: Saving memory for {from_phone}")
                logger.info(f"   User: '{user_message_content[:50]}'")
                logger.info(f"   AI: '{last_reply[:50]}'")
                await save_user_interaction(
                    user_id=from_phone,
                    user_msg=user_message_content,
                    ai_msg=last_reply
                )
                logger.info(f"✅ Memory saved!")
            else:
                logger.warning(f"⚠️ Memory skip: user={bool(user_message_content)}, ai={bool(last_reply)}")
        except Exception as mem_err:
            logger.error(f"❌ Memory save error: {mem_err}")
        
        return {
            "status": "processed",
            "channel": "whatsapp",
            "user_id": from_phone,
            "send_result": send_result,
            "last_reply": last_reply
        }
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}")
        return {"status": "error"}

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
    from app.graphs.main_graph import app as graph_app
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
        
        # Construct Input State with ALL required fields
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
        
        # Invoke Graph
        logger.info(f"Invoking Agent Graph for IG User {sender_id}...")
        final_state = await graph_app.ainvoke(input_state, config={"configurable": {"thread_id": sender_id}})
        
        send_result = final_state.get("send_result")
        final_messages = final_state.get("messages", [])
        last_reply = final_messages[-1].content if final_messages else None
        
        # 🔥 FALLBACK: Save memory directly in webhook
        try:
            if text_content and last_reply:
                from app.tools.vector_tools import save_user_interaction
                logger.info(f"💾 Instagram: Saving memory for {sender_id}")
                await save_user_interaction(
                    user_id=sender_id,
                    user_msg=text_content,
                    ai_msg=last_reply
                )
                logger.info(f"✅ Instagram: Memory saved!")
        except Exception as mem_err:
            logger.error(f"❌ Instagram: Memory save error: {mem_err}")
        
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

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
        from_phone = message.from_  # The user's phone number (underscore because 'from' is Python keyword)
        
        # Extract customer info from contacts metadata
        customer_email = None
        customer_name = None
        
        contacts = value.contacts
        if contacts and len(contacts) > 0:
            contact = contacts[0]  # Now properly typed as WhatsAppContact!
            # Access using Pydantic model attributes
            if contact.profile:
                customer_name = contact.profile.name
            customer_email = contact.email  # Direct attribute access
            
        print(f"\n>>> WEBHOOK: Customer Info from Metadata")
        print(f">>> Phone: {from_phone}")
        print(f">>> Name: {customer_name or 'Not provided'}")
        print(f">>> Email: {customer_email or 'Not provided'}")        
        # Extract message content
        content = ""
        msg_type = message.type
        
        user_message_content = ""
        image_url = None
        
        print(f"\n>>> MESSAGE EXTRACTION DEBUG:")
        print(f">>> msg_type = {msg_type}")
        print(f">>> message object type = {type(message).__name__}")
        print(f">>> message.text = {message.text}")
        print(f">>> message.image = {message.image}")
        
        # Check for text content first (type field is unreliable)
        if message.text:
            text_obj = message.text
            print(f">>> text_obj = {text_obj}")
            print(f">>> text_obj type = {type(text_obj).__name__}")
            
            if hasattr(text_obj, 'body'):
                user_message_content = text_obj.body
                print(f">>> Extracted body = '{user_message_content}'")
            else:
                print(f">>> ERROR: text_obj has no body attribute")
                user_message_content = ""
                
        # Check for image content
        elif message.image:
            img_obj = message.image
            print(f">>> img_obj = {img_obj}")
            
            media_id = img_obj.id
            caption = img_obj.caption or ""
            user_message_content = caption
            print(f">>> Image caption = '{caption}'")
            
            # Resolve URL
            fetched_url = await meta_service.get_media_url(media_id)
            if fetched_url:
                image_url = fetched_url
            else:
                logger.warning(f"Could not resolve URL for media {media_id}")
        else:
            logger.warning(f"⚠️ Cannot extract message. Type: {msg_type}, Has text: {hasattr(message, 'text')}, Has image: {hasattr(message, 'image')}")
            
        print(f">>> FINAL user_message_content = '{user_message_content}' (length: {len(user_message_content)})")
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
        
        # Load full conversation history from Pinecone for context
        print(f"\n>>> LOADING CONVERSATION HISTORY FROM PINECONE <<<")
        from app.tools.vector_tools import get_full_conversation_history
        
        history_messages = await get_full_conversation_history(from_phone, max_messages=100)
        print(f">>> Found {len(history_messages)} previous messages")
        
        # Combine history + new message
        all_messages = history_messages + [human_msg]
        print(f">>> Total context: {len(all_messages)} messages (history + current)")
        
        # Construct Input State with ALL required fields
        input_state = {
            "messages": all_messages,  # FULL CONVERSATION CONTEXT!
            "user_id": from_phone,
            "session_id": from_phone,
            "platform": "whatsapp",
            "is_admin": False,
            "blocked": False,
            "order_intent": False,
            "requires_handoff": False,
            "query_type": "text",
            "last_user_message": user_message_content,
            # FIXED CONTEXT: Customer info from WhatsApp
            "customer_email": customer_email,  # From contacts metadata
            "customer_name": customer_name,    # From contacts metadata
            "user_name": customer_name or "Customer",  # Fallback for compatibility
        }
        
        # Invoke Graph
        print("\n>>> ABOUT TO INVOKE GRAPH <<<")
        print(f">>> User: {from_phone}")
        print(f">>> Input state keys: {list(input_state.keys())}")
        print(f">>> Messages in context: {len(all_messages)}")
        
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
        logger.error(f"WhatsApp processing error: {str(e)}")
        # Add detailed traceback for debugging
        import traceback
        traceback.print_exc()
        logger.error(f"Full traceback: {traceback.format_exc()}")
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

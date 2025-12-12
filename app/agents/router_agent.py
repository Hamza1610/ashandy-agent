from app.state.agent_state import AgentState
from app.tools.db_tools import check_admin_whitelist
from langchain_core.messages import HumanMessage
import logging
import json

logger = logging.getLogger(__name__)

async def router_agent_node(state: AgentState):
    """
    Router Agent: Classifies user and query type with robust logic.
    """
    try:
        messages = state.get("messages", [])
        if not messages:
            return {"error": "No messages to route."}
            
        last_message = messages[-1]
        sender_id = state.get("user_id", "unknown")
        
        logger.info(f"Router: Processing message. Type: {type(last_message).__name__}, Total messages: {len(messages)}")
        
        # 1. Check Admin Whitelist
        is_admin = False
        try:
            is_admin = await check_admin_whitelist.ainvoke(sender_id)
        except Exception as e:
            logger.error(f"Whitelist check failed: {e}")
            
        # 2. Determine Query Type (Text vs Image vs Command)
        query_type = "text" # default
        image_url = None
        
        if isinstance(last_message, HumanMessage):
             # Check for image content in message
             # Handle standard LangChain multimodal content type (list of dicts)
             if isinstance(last_message.content, list):
                 for content_part in last_message.content:
                     if isinstance(content_part, dict) and content_part.get("type") == "image_url":
                         image_url = content_part["image_url"].get("url")
                         query_type = "image"
                         break
             
             # Also check additional_kwargs as fallback (webhook might populate this)
             if not image_url and last_message.additional_kwargs.get("image_url"):
                 image_url = last_message.additional_kwargs["image_url"]
                 query_type = "image"

        # Admin commands check (Overrules standard text/image if admin)
        content_text = ""
        if isinstance(last_message, HumanMessage):
            logger.info(f"Router: HumanMessage detected. Content type: {type(last_message.content).__name__}")
            if isinstance(last_message.content, str):
                content_text = last_message.content
                logger.info(f"Router: Extracted string content: '{content_text[:50]}'")
            elif isinstance(last_message.content, list):
                logger.info(f"Router: Content is list with {len(last_message.content)} items")
                # Extract text part
                for part in last_message.content:
                     if isinstance(part, dict) and part.get("type") == "text":
                         content_text = part.get("text", "")
                         logger.info(f"Router: Extracted text from list: '{content_text[:50]}'")
            else:
                logger.warning(f"Router: Unexpected content type: {type(last_message.content)}")
                # Fallback: try to convert to string
                content_text = str(last_message.content) if last_message.content else ""
        elif isinstance(last_message, dict):
            logger.info(f"Router: Message is dict. Keys: {list(last_message.keys())}")
            content_text = str(last_message.get("content", ""))
            logger.info(f"Router: Extracted dict content: '{content_text[:50]}'")
        else:
            logger.warning(f"Router: Unknown message type: {type(last_message)}")

        if is_admin and content_text.strip().startswith("/"):
            query_type = "admin_command"
            state["admin_command"] = content_text.strip()

        # Store the extracted content_text as last_user_message for memory saving
        # If content_text is empty, try direct extraction as fallback
        last_user_message = content_text.strip() if content_text else ""
        
        # Fallback: if still empty, try to get it directly from the message
        if not last_user_message and isinstance(last_message, HumanMessage):
            try:
                # Try to get content directly
                if hasattr(last_message, 'content'):
                    raw_content = last_message.content
                    if isinstance(raw_content, str) and raw_content:
                        last_user_message = raw_content.strip()
                    elif raw_content:
                        last_user_message = str(raw_content).strip()
            except Exception as e:
                logger.warning(f"Router: Fallback extraction failed: {e}")
        
        logger.info(f"Router: last_message type={type(last_message).__name__}, content_text='{content_text[:50] if content_text else 'EMPTY'}', last_user_message='{last_user_message[:50] if last_user_message else 'EMPTY'}'")

        # Log if image detected
        if image_url:
            print(f"\n>>> ROUTER: Image detected! query_type={query_type}")
            print(f">>> ROUTER: Image URL = {image_url[:80]}...")
            logger.info(f"Image detected for visual search: {image_url}")

        # -----------------------------
        # SMART FILTERING (Anti-Spam)
        # -----------------------------
        # Prevent bot from replying to low-value messages (Story reactions, 'lol', 'ok', etc.)
        # Only filter if NO image is present (images are usually intentful)
        if not image_url and not is_admin and query_type != "admin_command":
            import re
            
            clean_text = content_text.strip().lower()
            
            # 1. Check for meaningful alphanumerics (exclude emojis)
            # Remove non-alphanumeric chars (except basic punctuation used in questions)
            # If the result is empty or just 1 char, it's likely just emojis ("🔥🔥") or "?"
            alpha_text = re.sub(r'[^a-z0-9]', '', clean_text)
            
            should_ignore = False
            
            # Condition A: Mostly Emojis / Symbols
            if len(alpha_text) == 0 and len(clean_text) > 0:
                should_ignore = True
                logger.info(f"Router: Ignoring message (Only Symbols/Emojis): '{clean_text}'")

            # Condition B: Very short, non-question reactions
            # e.g. "k", "ok", "lol", "nice", "uu"
            ignore_keywords = {"k", "kk", "ok", "okay", "lol", "lmao", "nice", "cool", "wow", "yep", "yes", "no", "thanks", "thx"}
            if clean_text in ignore_keywords:
                should_ignore = True
                logger.info(f"Router: Ignoring message (Casual Reaction): '{clean_text}'")

            # Condition C: Explicit short filtering
            if len(clean_text) < 2 and clean_text not in ["y", "n"]: # Allow Y/N for some flows, looking unlikely here though
                 should_ignore = True
                 logger.info(f"Router: Ignoring message (Too Short): '{clean_text}'")

            # EXCEPTION: If text looks like a question or has intent keywords, DO NOT IGNORE
            intent_keywords = {"how", "price", "cost", "much", "buy", "get", "where", "need", "want", "available", "stock", "fake", "original"}
            if any(k in clean_text for k in intent_keywords) or "?" in content_text:
                should_ignore = False
                logger.info("Router: Message kept (Intent/Question detected)")

            if should_ignore:
                query_type = "ignore"

        return {
            "is_admin": is_admin,
            "query_type": query_type,
            "image_url": image_url,
            "last_user_message": last_user_message
        }

    except Exception as e:
        logger.error(f"Router Agent Error: {e}")
        return {"error": str(e)}


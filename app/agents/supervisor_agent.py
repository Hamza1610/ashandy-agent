"""
Supervisor Agent: Input/Output gatekeeper for safety, spam filtering, caching, and feedback.
"""
from app.state.agent_state import AgentState
from app.tools.llama_guard_tool import check_safety
from app.services.logging_service import logging_service
from app.services.sentiment_service import sentiment_service
from app.services.profile_service import profile_service
from app.services.policy_service import policy_service
from app.services.response_cache_service import response_cache_service
from app.services.feedback_service import feedback_service
from langchain_core.messages import AIMessage
import logging
import re

logger = logging.getLogger(__name__)

CONSULTATION_KEYWORDS = {
    "consultation", "consult", "dermatologist", "doctor", 
    "skin analysis", "diagnose", "diagnosis", "prescription", 
    "medical advice", "what's this rash", "is this acne"
}


async def supervisor_agent_node(state: AgentState):
    """
    Input Supervisor: Filters spam, checks cache, checks safety.
    Returns: supervisor_verdict = "safe" | "block" | "ignore" | "cached"
    """
    try:
        logger.info("🚦 SUPERVISOR ENTRY - Function started")
        messages = state.get("messages", [])
        if not messages:
            return {"supervisor_verdict": "ignore"}
            
        last_message = messages[-1]
        
        # Mark message as read for instant feedback
        msg_id = last_message.additional_kwargs.get("id") or getattr(last_message, "id", None)
        if msg_id and state.get("platform") == "whatsapp":
            from app.services.meta_service import meta_service
            await meta_service.mark_whatsapp_message_read(msg_id)
            
        # Extract content
        content_text = ""
        if hasattr(last_message, "content"):
            if isinstance(last_message.content, str):
                content_text = last_message.content
            elif isinstance(last_message.content, list):
                for part in last_message.content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        content_text = part.get("text", "")
                        break
        
        clean_text = content_text.strip().lower()
        logger.info(f"Supervisor: Analyzing input: '{clean_text[:50]}...'")

        # Check for image presence
        has_image = bool(
            state.get("image_url") or 
            last_message.additional_kwargs.get("image_url") or
            (isinstance(last_message.content, list) and 
             any(p.get("type") == "image_url" for p in last_message.content if isinstance(p, dict)))
        )
        is_admin = state.get("is_admin", False)
        user_id = state.get("user_id", "unknown")

        # NDPR: /delete_memory command (Right to be Forgotten)
        if clean_text in ["/delete_memory", "/deletememory", "delete my memory", "delete my data"]:
            logger.info(f"Supervisor: NDPR deletion request from {user_id}")
            try:
                from app.services.ndpr_service import ndpr_service
                result = await ndpr_service.delete_user_memory(user_id)
                return {
                    "supervisor_verdict": "block",
                    "messages": [AIMessage(content=result["message"])]
                }
            except Exception as e:
                logger.error(f"NDPR deletion failed: {e}")
                return {
                    "supervisor_verdict": "block",
                    "messages": [AIMessage(content="⚠️ Unable to process deletion request. Please contact the manager for assistance.")]
                }

        if not has_image and not is_admin:
            # Filter: Emoji/symbol only
            alpha_text = re.sub(r'[^a-z0-9]', '', clean_text)
            if len(alpha_text) == 0 and len(clean_text) > 0:
                logger.info("Supervisor: Ignored (Emoji/Symbol only)")
                return {"supervisor_verdict": "ignore"}
                
            # Filter: Casual reactions
            ignore_keywords = {"k", "kk", "ok", "okay", "lol", "lmao", "nice", "cool", "wow", "yep", "yes", "no", "thanks", "thx"}
            if clean_text in ignore_keywords:
                logger.info("Supervisor: Ignored (Casual reaction)")
                return {"supervisor_verdict": "ignore"}
            
            # Fast-path: Greetings
            greeting_keywords = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening"}
            if clean_text in greeting_keywords or clean_text.startswith("hi ") or clean_text.startswith("hello "):
                logger.info("Supervisor: Fast-path greeting response")
                return {
                    "supervisor_verdict": "block",
                    "messages": [AIMessage(content="Hello! 👋 Welcome to Ashandy Home of Cosmetics. I am Awéléwà, the AI sales and customer support agent for ASHANDY HOME OF COSMETICS. How can I help you today?")]
                }

            # === CACHE CHECK (before LLM processing) ===
            cached_response = await response_cache_service.get_cached_response(content_text, user_id)
            if cached_response:
                logger.info(f"Supervisor: Cache HIT - returning cached response")
                return {
                    "supervisor_verdict": "cached",
                    "cached_response": cached_response,
                    "messages": [AIMessage(content=cached_response)]
                }

        # Consultation policy check
        if any(k in clean_text for k in CONSULTATION_KEYWORDS):
            logger.info("Supervisor: Consultation requested - Policy Enforcement")
            store_policy = policy_service.get_policy_summary("store_info", max_lines=5) or ""
            msg = ("Thank you for trusting us! ❤️\n"
                   "However, for professional skin consultations and analysis, "
                   "we require you to visit our physical shop to see the Manager.\n\n"
                   "📍 *Ashandy Home of Cosmetics*\n"
                   "Shop 9 & 10, Divine Favor Plaza, Iyaganku, Ibadan\n\n"
                   "Our manager can assess your skin and recommend the right products. "
                   "Meanwhile, if you already know what you want, I can help you order right away! 🛍️")
            return {
                "supervisor_verdict": "block",
                "messages": [AIMessage(content=msg)]
            }

        # Safety check (Llama Guard)
        if len(clean_text) > 5 and not is_admin:
            safety_res = await check_safety.ainvoke(content_text)
            if safety_res.lower().startswith("unsafe"):
                logger.warning(f"Supervisor: Unsafe content detected: {safety_res}")
                return {
                    "supervisor_verdict": "block",
                    "messages": [AIMessage(content="I cannot respond to that message due to safety guidelines.")]
                }

        # Sentiment analysis and logging
        platform = state.get("platform", "whatsapp")
        sentiment_score = sentiment_service.analyze(content_text)
        intent = sentiment_service.classify_intent(content_text)
        
        # Feedback detection and logging (for online learning)
        previous_ai_response = None
        if len(messages) > 1:
            for msg in reversed(messages[:-1]):
                if isinstance(msg, AIMessage):
                    previous_ai_response = msg.content[:500] if msg.content else None
                    break
        
        await feedback_service.detect_and_log_feedback(
            user_id=user_id,
            message=content_text,
            previous_ai_response=previous_ai_response,
            context_topic=intent
        )
        
        await logging_service.log_message(
            user_id=user_id,
            role="user",
            content=content_text,
            sentiment_score=sentiment_score,
            intent=intent,
            platform=platform
        )
        await profile_service.update_on_message(user_id, sentiment_score)
        
        # Store original message for cache key later
        logger.info(f"Supervisor: Input Safe. Sentiment={sentiment_score:.2f}, Intent={intent}")
        return {
            "supervisor_verdict": "safe",
            "last_user_message": content_text  # For caching the response later
        }
    except Exception as e:
        logger.error(f"❌ SUPERVISOR CRASHED: {type(e).__name__}: {e}", exc_info=True)
        # Return "safe" to continue processing despite error
        return {"supervisor_verdict": "safe"}


async def output_supervisor_node(state: AgentState):
    """
    Output Supervisor: Validates AI responses, truncates for WhatsApp, caches responses.
    Returns: supervisor_output_verdict = "safe" | "block"
    """
    messages = state.get("messages", [])
    if not messages:
        return {"supervisor_output_verdict": "safe"}
        
    last_message = messages[-1]
    if not isinstance(last_message, AIMessage):
        return {"supervisor_output_verdict": "safe"}
         
    content = last_message.content
    
    # WhatsApp length limit (500 chars)
    MAX_WHATSAPP_CHARS = 500
    if content and len(content) > MAX_WHATSAPP_CHARS:
        truncated = content[:MAX_WHATSAPP_CHARS]
        last_period = truncated.rfind('.')
        last_exclaim = truncated.rfind('!')
        last_question = truncated.rfind('?')
        cut_point = max(last_period, last_exclaim, last_question)
        if cut_point > MAX_WHATSAPP_CHARS * 0.6:
            content = truncated[:cut_point + 1]
        else:
            content = truncated.rstrip() + "..."
        last_message.content = content
        logger.info(f"Output Supervisor: Truncated response to {len(content)} chars")
    
    # Block stack traces
    if "Traceback" in content or "Error:" in content:
        if "File \"" in content and "line" in content:
            logger.warning("Output Supervisor: Blocked stack trace leak.")
            return {
                "supervisor_output_verdict": "block",
                "messages": [AIMessage(content="I encountered a technical issue. Please try again.")]
            }

    # Safety check
    if len(content) > 10:
        safety_res = await check_safety.ainvoke(content)
        if safety_res.lower().startswith("unsafe"):
            logger.warning(f"Output Supervisor: Unsafe output detected: {safety_res}")
            return {
                "supervisor_output_verdict": "block",
                "messages": [AIMessage(content="My response was flagged by safety guidelines. I cannot send it.")]
            }
    
    # === CACHE THE RESPONSE ===
    original_query = state.get("last_user_message", "")
    if original_query and content:
        await response_cache_service.cache_response(original_query, content)
    
    # Log AI response
    user_id = state.get("user_id", "unknown")
    platform = state.get("platform", "whatsapp")
    await logging_service.log_message(
        user_id=user_id,
        role="assistant",
        content=content,
        sentiment_score=0.0,
        intent=None,
        platform=platform
    )
             
    logger.info("Output Supervisor: Response Safe.")
    return {"supervisor_output_verdict": "safe"}

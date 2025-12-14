from app.state.agent_state import AgentState
from app.tools.llama_guard_tool import check_safety
from app.services.logging_service import logging_service
from app.services.sentiment_service import sentiment_service
from app.services.profile_service import profile_service
from app.services.policy_service import policy_service
from langchain_core.messages import AIMessage
import logging
import re

logger = logging.getLogger(__name__)

# Consultation keywords (from docs/policies/consultation.md)
CONSULTATION_KEYWORDS = {
    "consultation", "consult", "dermatologist", "doctor", 
    "skin analysis", "diagnose", "diagnosis", "prescription", 
    "medical advice", "what's this rash", "is this acne"
}

async def supervisor_agent_node(state: AgentState):
    """
    Supervisor Agent: The Gatekeeper.
    
    Responsibilities:
    1. Safety Check (Llama Guard): Filters violence, hate, etc.
    2. Anti-Spam (Regex): Filters 'lol', emoji-only messages.
    3. Handover Check: Detects explicit requests for human/manager.
    
    Outputs:
    - supervisor_verdict: "safe", "block", "handoff", "ignore"
    """
    messages = state.get("messages", [])
    if not messages:
        return {"supervisor_verdict": "ignore"}
        
    last_message = messages[-1]
    
    # --- INSTANT FEEDBACK: Mark as Read ---
    # Attempt to extract message ID from 'additional_kwargs' or standard 'id' field
    msg_id = last_message.additional_kwargs.get("id") or getattr(last_message, "id", None)
    if msg_id and state.get("platform") == "whatsapp":
        from app.services.meta_service import meta_service
        # Fire and forget (don't await strictly if you want max speed, but await is safer for now)
        await meta_service.mark_whatsapp_message_read(msg_id)
        
    content_text = ""
    
    # Extract content safely
    if hasattr(last_message, "content"):
        if isinstance(last_message.content, str):
            content_text = last_message.content
        elif isinstance(last_message.content, list):
            # Extract first text part
            for part in last_message.content:
                 if isinstance(part, dict) and part.get("type") == "text":
                     content_text = part.get("text", "")
                     break
    
    clean_text = content_text.strip().lower()
    logger.info(f"Supervisor: Analyzing input: '{clean_text[:50]}...'")

    # -----------------------------
    # 1. ANTI-SPAM (Fast Regex)
    # -----------------------------
    # Only if NOT an image (image usually implies intent)
    # Check for image presence in state
    has_image = bool(state.get("image_url") or 
                     (last_message.additional_kwargs.get("image_url")) or
                     (isinstance(last_message.content, list) and 
                      any(p.get("type") == "image_url" for p in last_message.content if isinstance(p, dict))))

    is_admin = state.get("is_admin", False)

    if not has_image and not is_admin:
        # Filter 1: Only symbols/emojis
        alpha_text = re.sub(r'[^a-z0-9]', '', clean_text)
        if len(alpha_text) == 0 and len(clean_text) > 0:
            logger.info("Supervisor: Ignored (Emoji/Symbol only)")
            return {"supervisor_verdict": "ignore"}
            
        # Filter 2: Casual short reactions
        ignore_keywords = {"k", "kk", "ok", "okay", "lol", "lmao", "nice", "cool", "wow", "yep", "yes", "no", "thanks", "thx"}
        if clean_text in ignore_keywords:
            logger.info("Supervisor: Ignored (Casual reaction)")
            return {"supervisor_verdict": "ignore"}

    # Consultation Policy Check (keywords from policy file)
    if any(k in clean_text for k in CONSULTATION_KEYWORDS):
        logger.info("Supervisor: Consultation requested - Policy Enforcement")
        
        # Get store info from policy for personalized response
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

    # -----------------------------
    # 2. HANDOVER CHECK (Explicit) - REMOVED per Policy Update
    # -----------------------------
    # Policy: Do not pass to manager immediately. Agent must try to help first.
    # We let this flow through to the Planner/Sales Agent.
    
    # (Original Handover Logic Removed)

    # -----------------------------
    # 3. SAFETY CHECK (Llama Guard)
    # -----------------------------
    # Skip for very short text to save latency/cost, unless it looks suspicious? 
    # For now, apply to everything substantial.
    if len(clean_text) > 5 and not is_admin:
        safety_res = await check_safety.ainvoke(content_text)
        if safety_res.lower().startswith("unsafe"):
            logger.warning(f"Supervisor: Unsafe content detected: {safety_res}")
            return {
                "supervisor_verdict": "block",
                "messages": [AIMessage(content="I cannot respond to that message due to safety guidelines.")]
            }

    # -----------------------------
    # 4. LOG INPUT & ANALYZE SENTIMENT
    # -----------------------------
    user_id = state.get("user_id", "unknown")
    platform = state.get("platform", "whatsapp")
    
    # Analyze sentiment
    sentiment_score = sentiment_service.analyze(content_text)
    intent = sentiment_service.classify_intent(content_text)
    
    # Log the message
    await logging_service.log_message(
        user_id=user_id,
        role="user",
        content=content_text,
        sentiment_score=sentiment_score,
        intent=intent,
        platform=platform
    )
    
    # Update customer profile
    await profile_service.update_on_message(user_id, sentiment_score)
    
    logger.info(f"Supervisor: Input Safe. Sentiment={sentiment_score:.2f}, Intent={intent}")
    return {"supervisor_verdict": "safe"}

async def output_supervisor_node(state: AgentState):
    """
    Output Supervisor: Final Gatekeeper.
    
    Responsibilities:
    1. Check Final AI Response for Safety and Policy Compliance.
    2. Ensure no 'trace' or debug info leaked.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"supervisor_output_verdict": "safe"}
        
    last_message = messages[-1]
    
    # Only check if it's an AI message
    if not isinstance(last_message, AIMessage):
         return {"supervisor_output_verdict": "safe"}
         
    content = last_message.content
    
    # 1. Regex Checks (Anti-Leak)
    if "Traceback" in content or "Error:" in content:
        # Allow "Error:" if it's a polite user message, but block stack traces
        if "File \"" in content and "line" in content:
             logger.warning("Output Supervisor: Blocked stack trace leak.")
             return {
                 "supervisor_output_verdict": "block",
                 "messages": [AIMessage(content="I encountered a technical issue. Please try again.")]
             }

    # 2. Safety Check (Llama Guard) - Reuse input check logic/tool
    # Skip for short functional replies to save latency
    if len(content) > 10:
        safety_res = await check_safety.ainvoke(content)
        if safety_res.lower().startswith("unsafe"):
            logger.warning(f"Output Supervisor: Unsafe output detected: {safety_res}")
            return {
                "supervisor_output_verdict": "block",
                "messages": [AIMessage(content="My response was flagged by safety guidelines. I cannot send it.")]
            }
    
    # Log AI response
    user_id = state.get("user_id", "unknown")
    platform = state.get("platform", "whatsapp")
    
    await logging_service.log_message(
        user_id=user_id,
        role="assistant",
        content=content,
        sentiment_score=0.0,  # AI messages are neutral
        intent=None,
        platform=platform
    )
            
    logger.info("Output Supervisor: Response Safe.")
    return {"supervisor_output_verdict": "safe"}

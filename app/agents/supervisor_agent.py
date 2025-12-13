from app.state.agent_state import AgentState
from app.tools.llama_guard_tool import check_safety
from langchain_core.messages import AIMessage
import logging
import re

logger = logging.getLogger(__name__)

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

    # Consultation Policy Check
    consultation_keywords = {"consultation", "consult", "dermatologist", "doctor", "skin analysis", "diagnose", "prescription"}
    if any(k in clean_text for k in consultation_keywords):
        logger.info("Supervisor: Consultation requested - Policy Enforcement")
        msg = ("Thank you for trusting us! ❤️\n"
               "However, for professional skin consultations and analysis, "
               "we require you to visit our physical shop to see the Manager.\n\n"
               "📍 **Ashandy Cosmetics Shop**\n"
               "Please visit us for expert advice!")
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
    # 4. PASSED
    # -----------------------------
    logger.info("Supervisor: Input Safe. Passing to Planner.")
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
            
    logger.info("Output Supervisor: Response Safe.")
    return {"supervisor_output_verdict": "safe"}

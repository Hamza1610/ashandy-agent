from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.models.agent_states import AgentState
from app.agents.router_agent import router_agent_node
from app.agents.safety_agent import safety_agent_node
from app.agents.visual_search_agent import visual_search_agent_node
from app.agents.payment_order_agent import payment_order_agent_node
from app.agents.admin_agent import admin_agent_node
from app.agents.delivery_agent import delivery_agent_node
from app.agents.sales_consultant_agent import sales_consultant_agent_node
from app.tools.cache_tools import check_semantic_cache, update_semantic_cache
from app.tools.vector_tools import retrieve_user_memory, save_user_interaction
from app.tools.sentiment_tool import analyze_sentiment
from app.services.meta_service import meta_service
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import SystemMessage, HumanMessage
import hashlib
import logging

logger = logging.getLogger(__name__)

# -----------------------------
# Node Implementations
# -----------------------------

async def safety_log_node(state: AgentState):
    """
    Log unsafe content and terminate.
    """
    logger.warning(f"Safety violation for user {state.get('user_id')}: {state.get('messages')[-1].content}")
    return {"error": state.get("error", "unsafe")}


async def cache_check_node(state: AgentState):
    """
    Check Redis semantic cache for the latest user query.
    Uses last_user_message from state if available (set by router), otherwise extracts from messages.
    """
    # First try to use the value from router node
    last_user = state.get("last_user_message", "")
    
    # If not found, extract from messages
    if not last_user:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user = msg.content
                break
            # Also handle dict format
            if isinstance(msg, dict) and msg.get("type") in ["human", "HumanMessage", "Human"]:
                last_user = str(msg.get("content", ""))
                break
    
    if not last_user:
        return {}

    # Store/update in state for later use in response_node
    query_hash = hashlib.md5(last_user.encode()).hexdigest()
    cached = await check_semantic_cache.ainvoke(query_hash)
    if cached:
        logger.info("Semantic cache hit.")
        return {"cached_response": cached, "query_hash": query_hash, "last_user_message": last_user}
    return {"query_hash": query_hash, "last_user_message": last_user}


async def cache_hit_response_node(state: AgentState):
    """
    Wrap cached response into messages for downstream handling.
    """
    cached = state.get("cached_response")
    if not cached:
        return {}
    return {"messages": state.get("messages", []) + [SystemMessage(content=cached)]}


async def memory_retrieval_node(state: AgentState):
    """
    Retrieve user memory context from vector store.
    """
    user_id = state.get("user_id")
    user_memory = await retrieve_user_memory.ainvoke(user_id)
    return {"user_memory": user_memory}




async def cache_update_node(state: AgentState):
    """
    Update semantic cache with the latest assistant reply.
    """
    query_hash = state.get("query_hash")
    messages = state.get("messages", [])
    if not query_hash or not messages:
        return {}
    last_msg = messages[-1]
    if isinstance(last_msg, SystemMessage):
        await update_semantic_cache.ainvoke({"query_hash": query_hash, "response": last_msg.content})
    return {}


async def intent_detection_node(state: AgentState):
    """
    Detect purchase intent in user message or AI suggestion.
    """
    messages = state.get("messages", [])
    last_user = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user = msg.content
            break
    last_ai = ""
    for msg in reversed(messages):
        if isinstance(msg, SystemMessage):
            last_ai = msg.content
            break

    text = f"{last_user} {last_ai}".lower()
    intent = any(keyword in text for keyword in ["buy", "order", "pay", "purchase", "checkout"])
    return {"order_intent": intent}


async def webhook_wait_node(state: AgentState):
    """
    Placeholder for waiting on Paystack webhook; no-op for now.
    """
    return {}


async def sync_node(state: AgentState):
    """
    Placeholder POS sync hook.
    """
    return {}


async def notification_node(state: AgentState):
    """
    Notify user that payment is processing/complete.
    """
    user_id = state.get("user_id")
    platform = state.get("platform")
    message = "Your order is being processed. We will notify you once confirmed."

    if platform == "whatsapp":
        await meta_service.send_whatsapp_text(user_id, message)
    elif platform == "instagram":
        await meta_service.send_instagram_text(user_id, message)
    return {}


async def sentiment_node(state: AgentState):
    """
    Analyze sentiment of the last assistant response and flag for handoff if needed.
    """
    start_msg = ""
    messages = state.get("messages", [])
    
    # We want to analyze the USER's sentiment, not the AI's.
    # Try to get the last user message from state
    last_user = state.get("last_user_message")
    
    # Fallback: extract from messages if not in state
    if not last_user:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user = msg.content
                break
                
    if not last_user:
        return {}

    score = await analyze_sentiment.ainvoke(last_user)
    # Threshold: Lowered to -0.7 because the Agent now handles moderate complaints via tool.
    # We only want to flag EXTREME anger here as a safety net.
    is_negative = score < -0.7
    
    logger.info(f"Sentiment Analysis: Score={score}, Flagged={is_negative} (Text: '{last_user[:30]}...')")
    
    return {"sentiment_score": score, "requires_handoff": is_negative}



async def handoff_notification_node(state: AgentState):
    """
    Notify Admin/Manager of a negative sentiment/complaint.
    """
    user_id = state.get("user_id")
    sentiment_score = state.get("sentiment_score", 0.0)
    last_user = state.get("last_user_message", "Unknown")
    
    logger.warning(f"HANDOFF TRIGGERED for {user_id}. Sentiment: {sentiment_score}")
    
    if settings.ADMIN_PHONE_NUMBERS:
        manager_phone = settings.ADMIN_PHONE_NUMBERS[0]
        
        msg = (
            f"🚨 *EXTREME SENTIMENT ALERT*\n"
            f"👤 User: {user_id}\n"
            f"📉 Score: {sentiment_score}\n"
            f"------------------\n"
            f"User Said: \"{last_user}\"\n"
            f"------------------\n"
            f"⚠️ Bot detected hostility beyond normal complaint handling."
        )
        
        await meta_service.send_whatsapp_text(manager_phone, msg)
        
    return {}


async def output_safety_node(state: AgentState):
    """
    Check the Agent's generated response for safety violates before sending.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}
        
    last_msg = messages[-1]
    
    # Only check if the last message is from the AI (SystemMessage in this graph context, or AIMessage)
    # The SalesAgent returns SystemMessage(content=ai_message)
    if not isinstance(last_msg, SystemMessage):
        return {}
        
    content = last_msg.content
    if not content:
        return {}
        
    # Check Safety
    safety_res = await check_safety.ainvoke(content)
    
    if "unsafe" in safety_res.lower():
        logger.warning(f"OUTPUT SAFETY TRIGGERED. Blocked content: {content[:30]}...")
        # Replace the unsafe message with a safety fallback
        safe_replacement = SystemMessage(content="I apologize, but I cannot complete that response. How else can I assist you with Ashandy products?")
        
        # We need to replace the last message in the list.
        # LangGraph 'add_messages' appends, so we might need to be careful.
        # However, AgentState uses 'add_messages' reducer. 
        # To OVERWRITE, we might need to assume the graph handles replacement or we add a correction.
        # A simple append might look weird: "Bad Thing" -> "Sorry".
        # But since we haven't sent it to the user yet (response_node does the sending), 
        # we can just modify the state *if* we weren't using a reducer.
        # With 'add_messages', it's Append Only usually. 
        # Actually, let's just return a NEW message that apologizes. 
        # The 'response_node' sends the *last* message. 
        # So if we append the apology now, the response node will send the apology. 
        # The user will theoretically see "Bad Thing" then "Sorry" ?? 
        # NO. The response node sends the LAST message. 
        # BUT, the `response_node` is what sends to WhatsApp. 
        # So if we append here, `response_node` sends the Apology. The "Bad Thing" stays in history but isn't sent.
        # WAIT. `response_node` logic: `text = last.content`. 
        # So yes, appending works. The "Bad Thing" remains in internal agent memory but is NEVER sent to the user.
        
        return {"messages": [safe_replacement]}
        
    return {}


async def response_node(state: AgentState):
    """
    Send final response to the user via Meta channels.
    """
    user_id = state.get("user_id")
    platform = state.get("platform")
    messages = state.get("messages", [])
    text = ""
    if messages:
        last = messages[-1]
        if hasattr(last, "content"):
            text = last.content

    if not text:
        text = "Thank you for contacting us."

    send_result = {"status": "skipped"}
    if platform == "whatsapp":
        send_result = await meta_service.send_whatsapp_text(user_id, text)
    elif platform == "instagram":
        send_result = await meta_service.send_instagram_text(user_id, text)

    # --- SAVE MEMORY ---
    # We save the interaction *after* attempting to send, or even if sent.
    try:
        # First, try to use the stored last_user_message from router/cache_check_node
        last_human = state.get("last_user_message", "")
        
        logger.info(f"DEBUG: State keys: {list(state.keys())}")
        logger.info(f"DEBUG: last_user_message from state: '{last_human[:100] if last_human else 'EMPTY'}'")
        
        # If not found in state, try to extract from messages
        if not last_human:
            logger.info(f"DEBUG: last_user_message not in state, extracting from messages. Total: {len(messages)}")
            for idx, m in enumerate(reversed(messages)):
                logger.debug(f"DEBUG: Message {idx}: type={type(m).__name__}")
                # Handle LangChain HumanMessage object
                if isinstance(m, HumanMessage):
                    last_human = m.content if hasattr(m, 'content') else str(m)
                    logger.info(f"DEBUG: Found HumanMessage: {last_human[:50]}")
                    break
                # Handle Dict format
                if isinstance(m, dict):
                    msg_type = m.get("type", "")
                    content = m.get("content", "")
                    logger.debug(f"DEBUG: Dict message - type={msg_type}, content={str(content)[:50] if content else 'EMPTY'}")
                    if msg_type in ["human", "HumanMessage", "Human"] or (content and msg_type not in ["system", "ai", "assistant"]):
                        last_human = str(content) if content else ""
                        if last_human:
                            logger.info(f"DEBUG: Found human from dict: {last_human[:50]}")
                            break
        
        logger.info(f"DEBUG: Final last_human: {last_human[:100] if last_human else 'EMPTY'}")
        logger.info(f"DEBUG: AI text: {text[:100] if text else 'EMPTY'}")
        
        if last_human and text:
            logger.info(f"Saving interaction memory for {user_id}: user_msg='{last_human[:50]}...', ai_msg='{text[:50]}...'")
            # Call as normal async function (not a LangChain tool)
            save_res = await save_user_interaction(
                user_id=user_id, 
                user_msg=last_human, 
                ai_msg=text
            )
            logger.info(f"Memory Save Result: {save_res}")
        else:
            logger.warning(f"Memory Skipped. Human: {bool(last_human)}, AI: {bool(text)}")
            if not last_human:
                logger.warning(f"DEBUG: last_user_message in state: '{state.get('last_user_message', 'NOT FOUND')}'")
                logger.warning(f"DEBUG: All state keys: {list(state.keys())}")
            
    except Exception as e:
        logger.error(f"Background memory save failed: {e}", exc_info=True)

    # Attach send result back into state for upstream visibility
    return {"send_result": send_result}


async def admin_update_node(state: AgentState):
    """
    Placeholder for admin inventory/report updates (aligning with diagram).
    """
    return {}

# -----------------------------
# Conditional Routing
# -----------------------------

def route_after_router(state: AgentState):
    if state.get("is_admin"):
        return "admin"
    return "safety"


def route_after_safety(state: AgentState):
    if state.get("error"):
        return "safety_log"
    return "cache_check"


def route_after_cache(state: AgentState):
    if state.get("cached_response"):
        return "cache_hit_response"
    return "input_branch"


def route_input_branch(state: AgentState):
    if state.get("query_type") == "image":
        return "visual"
    return "memory"


def route_after_ai(state: AgentState):
    return "cache_update"


def route_after_cache_update(state: AgentState):
    return "intent"


def route_after_intent(state: AgentState):
    if state.get("order_intent"):
        return "payment"
    return "sentiment"


def route_after_payment(state: AgentState):
    return "webhook_wait"


def route_after_webhook_wait(state: AgentState):
    return "sync"


def route_after_sync(state: AgentState):
    return "notification"


def route_after_notification(state: AgentState):
    return "sentiment"


def route_after_sentiment(state: AgentState):
    if state.get("requires_handoff"):
        return "handoff_notification"
    if state.get("requires_handoff"):
        return "handoff_notification"
    return "output_safety"


def route_after_handoff(state: AgentState):
    return "output_safety"


def route_after_admin(state: AgentState):
    return "admin_update"


# -----------------------------
# Graph Construction
# -----------------------------

workflow = StateGraph(AgentState)

# Core nodes
workflow.add_node("router", router_agent_node)
workflow.add_node("safety", safety_agent_node)
workflow.add_node("safety_log", safety_log_node)
workflow.add_node("cache_check", cache_check_node)
workflow.add_node("cache_hit_response", cache_hit_response_node)
workflow.add_node("input_branch", lambda state: {})  # decision only
workflow.add_node("memory", memory_retrieval_node)
workflow.add_node("visual", visual_search_agent_node)
workflow.add_node("sales_agent", sales_consultant_agent_node)
workflow.add_node("cache_update", cache_update_node)
workflow.add_node("intent", intent_detection_node)
workflow.add_node("payment", payment_order_agent_node)
workflow.add_node("webhook_wait", webhook_wait_node)
workflow.add_node("sync", sync_node)
workflow.add_node("notification", notification_node)
workflow.add_node("sentiment", sentiment_node)
workflow.add_node("handoff_notification", handoff_notification_node)
workflow.add_node("output_safety", output_safety_node)
workflow.add_node("response", response_node)

# Admin path
workflow.add_node("admin", admin_agent_node)
workflow.add_node("admin_update", admin_update_node)

# Delivery
workflow.add_node("delivery_agent", delivery_agent_node)

# Edges
workflow.add_edge(START, "router")
workflow.add_conditional_edges("router", route_after_router)
workflow.add_conditional_edges("safety", route_after_safety)
workflow.add_conditional_edges("cache_check", route_after_cache)
workflow.add_edge("cache_hit_response", "response")
workflow.add_conditional_edges("input_branch", route_input_branch)
workflow.add_edge("visual", "sales_agent")
workflow.add_edge("memory", "sales_agent")
workflow.add_conditional_edges("sales_agent", route_after_ai)
workflow.add_conditional_edges("cache_update", route_after_cache_update)

# Modified Intent Routing to include Delivery Check
def route_after_intent_delivery(state: AgentState):
    # If order intent is present
    if state.get("order_intent"):
        # Check if we need delivery calculation (delivery type is delivery, but fee is not set)
        if state.get("delivery_type") == "delivery" and state.get("delivery_fee") is None:
            return "delivery_agent"
        return "payment"
    return "sentiment"

workflow.add_conditional_edges("intent", route_after_intent_delivery)

# Delivery Agent Edges
workflow.add_edge("delivery_agent", "payment") # In this simplified flow, we go to payment. Ideally back to Sales for invoice, but "Payment" can generate link which is the goal.

workflow.add_conditional_edges("payment", route_after_payment)
workflow.add_conditional_edges("webhook_wait", route_after_webhook_wait)
workflow.add_conditional_edges("sync", route_after_sync)
workflow.add_conditional_edges("notification", route_after_notification)
workflow.add_conditional_edges("sentiment", route_after_sentiment)
workflow.add_edge("handoff_notification", route_after_handoff)
workflow.add_edge("output_safety", "response")
workflow.add_edge("response", END)
workflow.add_edge("safety_log", END)

# Admin edges
workflow.add_edge("admin", "admin_update")
workflow.add_edge("admin_update", "output_safety")

# Compile
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

logger.info("LangGraph workflow compiled with full agentic flow alignment.")

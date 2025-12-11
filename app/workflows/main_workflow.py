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
from app.tools.vector_tools import retrieve_user_memory
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
    """
    messages = state.get("messages", [])
    last_user = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user = msg.content
            break
    if not last_user:
        return {}

    query_hash = hashlib.md5(last_user.encode()).hexdigest()
    cached = await check_semantic_cache.ainvoke(query_hash)
    if cached:
        logger.info("Semantic cache hit.")
        return {"cached_response": cached, "query_hash": query_hash}
    return {"query_hash": query_hash}


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
    messages = state.get("messages", [])
    last_ai = ""
    for msg in reversed(messages):
        if isinstance(msg, SystemMessage):
            last_ai = msg.content
            break
    if not last_ai:
        return {}

    score = await analyze_sentiment.ainvoke(last_ai)
    return {"sentiment_score": score, "requires_handoff": score < -0.5}


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
    return "response"


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
workflow.add_edge("response", END)
workflow.add_edge("safety_log", END)

# Admin edges
workflow.add_edge("admin", "admin_update")
workflow.add_edge("admin_update", "response")

# Compile
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

logger.info("LangGraph workflow compiled with full agentic flow alignment.")

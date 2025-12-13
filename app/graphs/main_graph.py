"""
Main LangGraph workflow for the Awelewa agent system.
This is the clean, modular implementation replacing main_workflow.py
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import ToolNode  # For automatic tool execution
from app.state.agent_state import AgentState
from app.agents.router_agent import router_agent_node
from app.agents.safety_agent import safety_agent_node
from app.agents.visual_search_agent import visual_search_agent_node
from app.agents.payment_order_agent import payment_order_agent_node
from app.agents.delivery_agent import delivery_agent_node
from app.agents.admin_agent import admin_agent_node
from app.agents.sales_consultant_agent import sales_agent_node
from app.tools.cache_tools import check_semantic_cache, update_semantic_cache
from app.tools.vector_tools import retrieve_user_memory, save_user_interaction
from app.tools.sentiment_tool import analyze_sentiment
from app.services.meta_service import meta_service
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
import hashlib
import logging

logger = logging.getLogger(__name__)

# Sales agent tools for ToolNode
from app.tools.product_tools import search_products, check_product_stock
from app.tools.simple_payment_tools import request_payment_link  # Simple payment request
from app.tools.email_tools import request_customer_email  # Email collection
from app.tools.memory_tools import save_memory

# ========== HELPER NODES ==========

async def safety_log_node(state: AgentState):
    """Log unsafe content and terminate."""
    logger.warning(f"Safety violation for user {state.get('user_id')}: {state.get('messages')[-1].content}")
    return {"error": state.get("error", "unsafe")}


async def cache_check_node(state: AgentState):
    """Check Redis semantic cache for the latest user query."""
    last_user = state.get("last_user_message", "")
    
    if not last_user:
        messages = state.get("messages", [])
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
        return {"cached_response": cached, "query_hash": query_hash, "last_user_message": last_user}
    
    return {"query_hash": query_hash, "last_user_message": last_user}


async def cache_hit_response_node(state: AgentState):
    """Wrap cached response into messages."""
    cached = state.get("cached_response")
    if not cached:
        return {}
    return {"messages": [AIMessage(content=cached)]}


async def memory_retrieval_node(state: AgentState):
    """
    Retrieve user memory context from vector store.
    
    This provides the agent with:
    - Past conversation history
    - User preferences (skin type, budget, etc.)
    - Previous purchases
    - Product interests
    """
    user_id = state.get("user_id")
    
    logger.info(f"🧠 Retrieving memory for user: {user_id}")
    
    try:
        user_memory = await retrieve_user_memory.ainvoke(user_id)
        
        # Log what we retrieved
        if user_memory and "No previous memory" not in user_memory:
            logger.info(f"✅ Memory found for {user_id}: {user_memory[:100]}...")
        else:
            logger.info(f"ℹ️  No previous memory for {user_id} (new customer)")
        
        return {"user_memory": user_memory}
        
    except Exception as e:
        logger.error(f"❌ Memory retrieval failed for {user_id}: {e}")
        return {"user_memory": "Memory retrieval failed. Treating as new customer."}


async def cache_update_node(state: AgentState):
    """Update semantic cache with the latest assistant reply."""
    query_hash = state.get("query_hash")
    messages = state.get("messages", [])
    
    if not query_hash or not messages:
        return {}
    
    last_msg = messages[-1]
    if hasattr(last_msg, 'content'):
        await update_semantic_cache.ainvoke({
            "query_hash": query_hash,
            "response": last_msg.content
        })
    
    return {}


async def intent_detection_node(state: AgentState):
    """
    Detect purchase intent in USER messages ONLY.
    
    CRITICAL: Only check what the USER said, not what the AI responded.
    This prevents false positives when AI mentions payment links.
    """
    # FIRST: Check if sales agent already set order_intent
    existing_intent = state.get("order_intent", False)
    
    print(f"\n>>> INTENT DETECTION: order_intent from state = {existing_intent}")
    
    if existing_intent:
        print(f">>> INTENT DETECTION: ✓ Preserving order_intent=True")
        return {"order_intent": True}
    
    # SECOND: Check if request_payment_link tool was called
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # Check if this is a payment link request
            if "payment link requested" in msg.content.lower() or "request_payment_link" in str(msg):
                print(f">>> INTENT DETECTION: ✓ Found request_payment_link tool call")
                return {"order_intent": True}
        # Check if AI message has tool calls for payment
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('name') == 'request_payment_link':
                    print(f">>> INTENT DETECTION: ✓ Found request_payment_link in tool_calls")
                    return {"order_intent": True}
    
    # FALLBACK: Check user keywords
    # Get the last USER message only
    last_user = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user = msg.content
            break
    
    # Only analyze user's message for purchase keywords
    if not last_user:
        return {"order_intent": False}
    
    user_text_lower = last_user.lower()
    
    # NO KEYWORD FALLBACK!
    # Trust the sales agent's intelligence - if it didn't call request_payment_link,
    # then there's no payment intent. This prevents false positives like
    # "I paid already" triggering payment flow.
    
    print(f">>> INTENT DETECTION: No payment tool call found → order_intent=False")
    logger.info(f"Intent detection: No request_payment_link tool - no order intent")
    
    return {"order_intent": False}


async def sentiment_node(state: AgentState):
    """Analyze sentiment of the last assistant response."""
    messages = state.get("messages", [])
    
    last_ai = ""
    for msg in reversed(messages):
        if hasattr(msg, 'content') and not isinstance(msg, HumanMessage):
            last_ai = msg.content
            break
    
    if not last_ai:
        return {}
    
    score = await analyze_sentiment.ainvoke(last_ai)
    return {"sentiment_score": score, "requires_handoff": score < -0.5}


async def response_node(state: AgentState):
    """Send final response to the user via Meta channels."""
    user_id = state.get("user_id")
    platform = state.get("platform")
    messages = state.get("messages", [])
    
    text = ""
    # Find last AI message with actual text (skip tool calls)
    for msg in reversed(messages):
        # Skip human messages
        if isinstance(msg, HumanMessage):
            continue
            
        # Check if message has content
        if hasattr(msg, "content") and msg.content:
            # Skip if it's just a tool call (empty content)
            if hasattr(msg, 'tool_calls') and msg.tool_calls and not msg.content.strip():
                logger.info(f"Skipping tool call message")
                continue
                
            text = msg.content
            logger.info(f"Found AI response: '{text[:100]}'")
            break
    
    if not text:
        text = "Thank you for contacting us."
        logger.warning(f"No AI response found, using fallback")
    
    logger.info(f"RESULT FROM AGENT: {text}")
    
    # Send via platform
    send_result = {"status": "skipped"}
    if platform == "whatsapp":
        send_result = await meta_service.send_whatsapp_text(user_id, text)
    elif platform == "instagram":
        send_result = await meta_service.send_instagram_text(user_id, text)
    
    # Save memory
    try:
        last_human = state.get("last_user_message", "")
        
        if not last_human:
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    last_human = m.content if hasattr(m, 'content') else str(m)
                    break
        
        if last_human and text:
            logger.info(f"Saving interaction memory for {user_id}")
            await save_user_interaction(
                user_id=user_id,
                user_msg=last_human,
                ai_msg=text
            )
        else:
            logger.warning(f"Memory skipped. Human: {bool(last_human)}, AI: {bool(text)}")
            
    except Exception as e:
        logger.error(f"Memory save failed: {e}", exc_info=True)
    
    return {"send_result": send_result}


async def admin_update_node(state: AgentState):
    """Placeholder for admin inventory/report updates."""
    return {}


async def webhook_wait_node(state: AgentState):
    """Placeholder for waiting on Paystack webhook."""
    return {}


async def sync_node(state: AgentState):
    """Placeholder POS sync hook."""
    return {}


async def notification_node(state: AgentState):
    """Notify user that payment is processing."""
    user_id = state.get("user_id")
    platform = state.get("platform")
    message = "Your order is being processed. We will notify you once confirmed."
    
    if platform == "whatsapp":
        await meta_service.send_whatsapp_text(user_id, message)
    elif platform == "instagram":
        await meta_service.send_instagram_text(user_id, message)
    
    return {}


# ========== ROUTING FUNCTIONS ==========

def route_after_router(state: AgentState):
    """Route based on admin status."""
    is_admin = state.get("is_admin")
    route = "admin" if is_admin else "safety"
    print(f"\n>>> ROUTING: after_router → {route}")
    logger.info(f"🔀 route_after_router → {route}")
    return route


def route_after_safety(state: AgentState):
    """Check if message was blocked."""
    error = state.get("error")
    route = "safety_log" if error else "input_branch"  # BYPASS cache - go straight to input_branch
    print(f">>> ROUTING: after_safety → {route}")
    logger.info(f"🔀 route_after_safety → {route}")
    return route


def route_after_cache(state: AgentState):
    """Check for cache hit."""
    cached = state.get("cached_response")
    route = "cache_hit_response" if cached else "input_branch"
    print(f">>> ROUTING: after_cache (cached={bool(cached)}) → {route}")
    logger.info(f"🔀 route_after_cache → {route}")
    return route


def route_input_branch(state: AgentState):
    """Route by query type (image vs text)."""
    query_type = state.get("query_type")
    route = "visual" if query_type == "image" else "memory"
    print(f">>> ROUTING: input_branch (query_type={query_type}) → {route}")
    logger.info(f"🔀 route_input_branch: query_type={query_type} → {route}")
    return route


def route_after_intent(state: AgentState):
    """Route to payment if order intent detected."""
    order_intent = state.get("order_intent")
    route = "payment" if order_intent else "sentiment"
    print(f"\n>>> ROUTING: after_intent (order_intent={order_intent}) → {route}")
    logger.info(f"🔀 route_after_intent: order_intent={order_intent} → {route}")
    return route


def route_after_payment(state: AgentState):
    """After payment link generated, go to delivery."""
    return "delivery"


def route_after_webhook_wait(state: AgentState):
    """After webhook, sync to POS."""
    return "sync"


def route_after_sync(state: AgentState):
    """After sync, notify customer."""
    return "notification"


def route_after_notification(state: AgentState):
    """After notification, do sentiment analysis."""
    logger.info(f"🔀 route_after_notification → sentiment")
    return "sentiment"


def route_after_sales(state: AgentState):
    """Route after sales agent - check if tools need to be executed."""
    messages = state.get("messages", [])
    if not messages:
        return "cache_update"
    
    last_message = messages[-1]
    
    # Check if last message has tool_calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        print(f"\n>>> ROUTING: Sales agent requested tools, going to tool_execution")
        logger.info("🔀 route_after_sales: has tool_calls → tool_execution")
        return "tool_execution"
    
    # No tool calls, proceed to cache update
    print(f"\n>>> ROUTING: No tools needed, proceeding to cache_update")
    logger.info("🔀 route_after_sales: no tool_calls → cache_update")
    return "cache_update"


def should_continue_after_tools(state: AgentState):
    """After tool execution, go back to sales agent for final response."""
    logger.info("🔀 after tools → sales (for final response)")
    return "sales"


# ========== GRAPH CONSTRUCTION ==========

# Create ToolNode with sales agent tools
sales_tools = [search_products, check_product_stock, request_customer_email, request_payment_link, save_memory]
tool_node = ToolNode(sales_tools)

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("router", router_agent_node)
workflow.add_node("safety", safety_agent_node)
workflow.add_node("safety_log", safety_log_node)
workflow.add_node("cache_check", cache_check_node)
workflow.add_node("cache_hit_response", cache_hit_response_node)
workflow.add_node("input_branch", lambda state: {})  # Decision point
workflow.add_node("memory", memory_retrieval_node)
workflow.add_node("visual", visual_search_agent_node)
workflow.add_node("sales", sales_agent_node)
workflow.add_node("tool_execution", tool_node)  # NEW: Automatic tool execution
workflow.add_node("cache_update", cache_update_node)
workflow.add_node("intent", intent_detection_node)
workflow.add_node("payment", payment_order_agent_node)
workflow.add_node("delivery", delivery_agent_node)  # NEW: Delivery coordinator
workflow.add_node("webhook_wait", webhook_wait_node)
workflow.add_node("sync", sync_node)
workflow.add_node("notification", notification_node)
workflow.add_node("sentiment", sentiment_node)
workflow.add_node("response", response_node)

# Admin path
workflow.add_node("admin", admin_agent_node)
workflow.add_node("admin_update", admin_update_node)

# Set entry point
workflow.add_edge(START, "router")

# Add conditional edges
workflow.add_conditional_edges("router", route_after_router)
workflow.add_conditional_edges("safety", route_after_safety)
workflow.add_conditional_edges("cache_check", route_after_cache)
workflow.add_conditional_edges("input_branch", route_input_branch)
workflow.add_conditional_edges("intent", route_after_intent)
workflow.add_conditional_edges("payment", route_after_payment)
workflow.add_edge("delivery", "sentiment")  # NEW: After delivery, analyze sentiment
workflow.add_conditional_edges("webhook_wait", route_after_webhook_wait)
workflow.add_conditional_edges("sync", route_after_sync)
workflow.add_conditional_edges("notification", route_after_notification)

# Add static edges
workflow.add_edge("cache_hit_response", "response")
workflow.add_edge("visual", "sales")
workflow.add_edge("memory", "sales")
workflow.add_conditional_edges("sales", route_after_sales)  # NEW: Check for tool calls
workflow.add_conditional_edges("tool_execution", should_continue_after_tools)  # NEW: Back to sales after tools
workflow.add_edge("cache_update", "intent")
workflow.add_edge("sentiment", "response")
workflow.add_edge("response", END)
workflow.add_edge("safety_log", END)

# Admin edges
workflow.add_edge("admin", "admin_update")
workflow.add_edge("admin_update", "response")

# ========== COMPILE GRAPH ==========
# 
# NOTE: PostgreSQL checkpointing temporarily disabled due to async incompatibility
# PostgresSaver doesn't support async operations (aget_tuple raises NotImplementedError)
# Our FastAPI app uses ainvoke (async) which requires async checkpointer
# 
# TODO: Research solutions:
# 1. Find async-compatible PostgreSQL checkpointer
# 2. Use aiosqlite or another async DB
# 3. Use custom async wrapper around PostgresSaver
# 4. Switch to sync invoke (not recommended for production)
#
# For now: System works WITHOUT conversation persistence
# Each webhook call starts fresh (no history)

print("\n=== Compiling LangGraph (Persistence Disabled) ===")
print("[INFO] Checkpointing disabled temporarily due to async compatibility")
print("[INFO] Each message will start with fresh state\n")

app = workflow.compile()  # No checkpointer

logger.info("[SUCCESS] Clean LangGraph workflow compiled successfully")





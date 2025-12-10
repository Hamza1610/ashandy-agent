from app.models.agent_states import AgentState
from app.tools.vector_tools import retrieve_user_memory
from app.tools.cache_tools import check_semantic_cache, update_semantic_cache
from app.tools.pos_connector_tools import search_phppos_products
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import hashlib

logger = logging.getLogger(__name__)

async def sales_consultant_agent_node(state: AgentState):
    """
    Sales Consultant: RAG + Conversational Sales (Llama 3 via Groq).
    """
    user_id = state.get("user_id")
    messages = state["messages"]
    last_message = messages[-1].content
    
    logger.info(f"Sales Consultant Agent processing message for user {user_id}: '{last_message}'")
    
    # 1. Check Semantic Cache
    query_hash = hashlib.md5(last_message.encode()).hexdigest()
    cached = await check_semantic_cache.ainvoke(query_hash)
    if cached:
        logger.info("Semantic cache hit.")
        state["cached_response"] = cached
        return {"cached_response": cached}
        
    # 2. Retrieve Context (User Memory)
    try:
        user_context = await retrieve_user_memory.ainvoke({"user_id": user_id})
        
    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}")
        user_context = "Memory unavailable."
    
    # 3. Formulate Prompt
    # Check if there are visual matches from previous node
    visual_context = ""
    if state.get("visual_matches"):
        visual_context = f"User uploaded an image. Visual matches found: {state['visual_matches']}"
        
    # NEW: Text Product Search Integration
    # If no visual matches, and query is text, check DB for product info explicitly
    text_context = ""
    query_type = state.get("query_type", "text")
    if query_type == "text":
        # We search using the last message as a loose keyword
        # In a real system, we'd extract keywords first.
        try:
             # Use PHPPOS Tool for live data
             search_res = await search_phppos_products.ainvoke(last_message)
             text_context = f"Live POS Product Search Results for '{last_message}':\n{search_res}"
        except Exception as e:
             logger.warning(f"POS search failed: {e}")
             
    system_prompt = f"""You are 'Sabi', a helpful and knowledgeable sales assistant for a cosmetics shop.
    
    User Context:
    {user_context}
    
    Visual Context (if any):
    {visual_context}
    
    Product Database Context (Live from PHPPOS):
    {text_context}
    
    Your goal is to help the customer, recommend products, and close sales. 
    1. ALWAYS use the 'Product Database Context' to verify Price and Stock availability before recommending.
    2. If a product is not in the context, apologize and say you can't find it.
    3. Be polite, concise, and professional. 
    4. If the user wants to buy, ask for confirmation to generate a payment link.
    """
    
    conversation = [("system", system_prompt)] + \
                   [("human", m.content) if isinstance(m, HumanMessage) else ("ai", m.content) for m in messages[-5:]] # Context window
                   
    # 4. Call LLM (Groq)
    try:
        if not settings.LLAMA_API_KEY:
             return {"error": "LLM API Key missing."}

        llm = ChatGroq(
            temperature=0.3,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        )
        
        response = await llm.ainvoke(conversation)
        ai_message = response.content
        
        # 5. Intent Detection (Simplified rule-based or second LLM call)
        # Check if user wants to buy
        if "buy" in last_message.lower() or "order" in last_message.lower() or "pay" in last_message.lower():
             state["order_intent"] = True
             
        # 6. Update Cache
        await update_semantic_cache.ainvoke({"query_hash": query_hash, "response": ai_message})
        
        # 7. Save Interaction to Memory
        try:
            from app.tools.vector_tools import save_user_interaction
            await save_user_interaction.ainvoke({
                "user_id": user_id, 
                "user_msg": last_message, 
                "ai_msg": ai_message
            })
        except Exception as e:
            logger.error(f"Background memory save failed: {e}")
        
        return {
            "messages": [SystemMessage(content=ai_message)],
            "order_intent": state.get("order_intent", False)
        }

    except Exception as e:
        logger.error(f"Sales Agent Error: {e}")
        return {"error": str(e)}

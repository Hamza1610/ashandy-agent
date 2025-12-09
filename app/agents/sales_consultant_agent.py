from app.models.agent_states import AgentState
from app.tools.vector_tools import retrieve_user_memory
from app.tools.cache_tools import check_semantic_cache, update_semantic_cache
from app.tools.db_tools import get_product_details
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
    
    # 1. Check Semantic Cache
    query_hash = hashlib.md5(last_message.encode()).hexdigest()
    cached = await check_semantic_cache.invoke(query_hash)
    if cached:
        logger.info("Semantic cache hit.")
        state["cached_response"] = cached
        return {"cached_response": cached}
        
    # 2. Retrieve Context (User Memory)
    user_context = await retrieve_user_memory.invoke(user_id)
    
    # 3. Formulate Prompt
    # Check if there are visual matches from previous node
    visual_context = ""
    if state.get("visual_matches"):
        visual_context = f"User uploaded an image. Visual matches found: {state['visual_matches']}"
        
    system_prompt = f"""You are 'Sabi', a helpful and knowledgeable sales assistant for a cosmetics shop.
    
    User Context:
    {user_context}
    
    Visual Context (if any):
    {visual_context}
    
    Your goal is to help the customer, recommend products, and close sales. 
    Be polite, concise, and professional. 
    If you recommend a product, mention its price.
    If the user wants to buy, ask for confirmation to generate a payment link.
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
            model_name="llama3-70b-8192"
        )
        
        response = await llm.ainvoke(conversation)
        ai_message = response.content
        
        # 5. Intent Detection (Simplified rule-based or second LLM call)
        # Check if user wants to buy
        if "buy" in last_message.lower() or "order" in last_message.lower() or "pay" in last_message.lower():
             state["order_intent"] = True
             
        # 6. Update Cache
        await update_semantic_cache.invoke({"query_hash": query_hash, "response": ai_message})
        
        return {
            "messages": [SystemMessage(content=ai_message)],
            "order_intent": state.get("order_intent", False)
        }

    except Exception as e:
        logger.error(f"Sales Agent Error: {e}")
        return {"error": str(e)}

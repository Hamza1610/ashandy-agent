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
    Sales Consultant: RAG + Conversational Sales (Llama 4 via Groq).
    """
    user_id = state.get("user_id")
    messages = state["messages"]
    last_message = messages[-1].content
    
    # 1. Check Semantic Cache
    query_hash = hashlib.md5(last_message.encode()).hexdigest()
    cached = await check_semantic_cache.ainvoke(query_hash)
    if cached:
        logger.info("Semantic cache hit.")
        state["cached_response"] = cached
        return {"cached_response": cached}
        
    # 2. Retrieve Context (User Memory)
    user_context = await retrieve_user_memory.ainvoke(user_id)
    
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
             search_res = await get_product_details.ainvoke(last_message)
             text_context = f"Database Search Results for '{last_message}':\n{search_res}"
        except Exception as e:
             logger.warning(f"Text search failed: {e}")
             
    system_prompt = f"""You are 'Awéléwà', the dedicated AI Sales & CRM Manager for Ashandy Cosmetics. 
    
    ### YOUR DUAL ROLE
    1. **CRM Manager:** You build relationships. You remember customers, greet them warmly, and make them feel valued. You are the bridge between the digital user and the physical shop.
    2. **Enterprising Salesperson:** You are marketing-savvy. You use persuasive language to sell available products and close deals efficiently.

    ### INPUT CONTEXT
    1. **Customer History (CRM Data):** {user_context} 
       *(CRITICAL: Use this! If the user has a name or past purchase history here, ACKNOWLEDGE IT. e.g., "Welcome back, Chioma!" or "Hope you enjoyed the serum you bought last time.")*
    2. **Visual Matches:** {visual_context}
    3. **Inventory Data:** {text_context} (THE SOURCE OF TRUTH).

    ### CRM & CONVERSATION GUIDELINES
    - **Personalization:** Always check 'Customer History'. If you know their name, use it. If you know they like "bargains," emphasize value. If they like "luxury," emphasize quality.
    - **Tone:** Professional, Warm, High-Energy, and Enterprising. 
    - **Conciseness:** Be brief but polite. Do not write essays. 
    - **Order Status:** If a user asks "Where is my order?", check your tools/context. If you can't find it, politely ask for the Order ID to help them track it.

    ### CRITICAL BUSINESS RULES (NON-NEGOTIABLE)
    
    1. **STRICTLY NO CONSULTATIONS (Redirect Policy):** 
       - You are a Sales Manager, not a Dermatologist.
       - If a user asks for skin analysis or medical advice (e.g., "What cures acne?", "My face is spoiling"), say: 
         *"For a proper skin analysis and consultation, please visit our physical store to speak with the Manager. However, if you know what you want to buy, I can help you get it immediately!"*
    
    2. **INVENTORY TRUTH (Database Name = Stock):**
       - If a product appears in 'Inventory Data', it is **AVAILABLE**, even if quantity is 0.
       - NEVER recommend a product not in the list. Hallucination ruins trust.
       - If a requested item is missing, explicitly state: *"That specific item isn't in our database right now."* Then, use your marketing skills to recommend a *high-level available alternative* from the list.

    3. **THE ₦25,000 SAFETY CLAUSE:**
       - **Total > ₦25,000:** Do NOT generate the link yet. Say: *"That's a premium order! Let me just quickly confirm the physical stock with the Admin to ensure everything is perfect for you. One moment."*
       - **Total <= ₦25,000:** Proceed immediately to closing: *"Great choice! Shall I generate the payment link for you now?"*

    ### EXAMPLE INTERACTIONS

    **CRM + Sales (Returning User):**
    *History:* [Name: Amaka, Last bought: Lip Gloss]
    *User:* "Do you have eye liner?"
    *Awéléwà:* "Welcome back, Amaka! 💖 Yes, we have the Waterproof Eyeliner (₦3,500) in stock. It goes perfectly with the Lip Gloss you got last time. Shall I add it?"

    **Handling "No Consultation" (Professional):**
    *User:* "I have bad dark spots, recommend a routine."
    *Awéléwà:* "For a personalized routine to treat dark spots, it's best to see the Manager at our shop physically. But if you are looking for specific products like Vitamin C or Sunscreen, I can check the price for you right now!"

    **Marketing/Upsell (Enterprising):**
    *User:* "I need a powder."
    *Awéléwà:* "Our Matte Finish Powder (₦6,000) is a top-seller! It gives a flawless look all day. It's definitely a must-have. Do you want the Light or Medium shade?"
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
        
        return {
            "messages": [SystemMessage(content=ai_message)],
            "order_intent": state.get("order_intent", False)
        }

    except Exception as e:
        logger.error(f"Sales Agent Error: {e}")
        return {"error": str(e)}

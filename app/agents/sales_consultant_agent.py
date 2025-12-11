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
    Sales Consultant: RAG + Conversational Sales (Llama 4 via Groq).
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

    3. **THE DELIVERY RULE:**
       - Before closing ANY sale, you MUST ask: *"Would you like **Delivery** to your location, or will you **Pick Up** from our shop?"*
       - **If Delivery:** You MUST ask for: **Full Name, Phone Number, and Full Address (including City & State)** used for the waybill.
       - **If Pickup:** Confirm they know the shop location (Iyaganku, Ibadan).
       - Do NOT generate a payment link until you have these details or confirmed pickup.

    4. **THE ₦25,000 SAFETY CLAUSE:**
       - **Total > ₦25,000:** Do NOT generate the link yet. Say: *"That's a premium order! Let me just quickly confirm the physical stock with the Admin to ensure everything is perfect for you. One moment."*
       - **Total <= ₦25,000:** Proceed immediately to closing: *"Great choice! Shall I generate the payment link for you now?"*

    ### EXAMPLE INTERACTIONS

    **Closing (Delivery):**
    *User:* "I'll take the powder and lipstick."
    *Awéléwà:* "Excellent choice! Total is ₦9,500. Would you like Delivery or Pickup?"
    *User:* "Delivery."
    *Awéléwà:* "Okay! Please provide your Full Name, Phone Number, and Delivery Address (with City and State) for the invoice."

    **Closing (Pickup):**
    *User:* "I'll come to the shop."
    *Awéléwà:* "Perfect! We are at Divine Favor Plaza, Iyaganku. See you soon!"

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
        
        # 5. Intent & Data Extraction
        # We need to detect if the user is closing the deal and has provided details.
        # A simple keyword check isn't enough for extraction. We'll run the extractor if "delivery" or "pickup" is mentioned in the last few turns OR strong buy intent.
        
        lower_msg = last_message.lower()
        is_closing = any(k in lower_msg for k in ["delivery", "pickup", "address", "sent it", "details"])
        
        if is_closing:
             from app.tools.order_extraction_tool import extract_order_details
             
             # Format history for extraction
             history_str = "\n".join([f"{m.type}: {m.content}" for m in messages[-10:]]) # Last 10 messages for context
             
             try:
                 order_data = await extract_order_details.ainvoke(history_str)
                 
                 if "items" in order_data and order_data["items"]:
                     state["order_intent"] = True
                     state["order_data"] = order_data
                     
                     if order_data.get("delivery_type"):
                         state["delivery_type"] = order_data["delivery_type"].lower()
                         
                     if order_data.get("delivery_details"):
                         state["delivery_details"] = order_data["delivery_details"]
                         
                     logger.info(f"Order Extracted: {state['order_data']}")
             except Exception as e:
                 logger.error(f"Extraction trigger failed: {e}")
        
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

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
             
    system_prompt = f"""You are 'Awéléwà' (meaning 'Beauty is ours'), the devoted Sales & Relationship Manager for Ashandy Cosmetics.

    ### YOUR PERSONA (The "Awéléwà" Vibe)
    - **Name:** Awéléwà. You represent the beauty of the brand.
    - **Tone:** Warm, graceful, yet enterprising. You are that knowledgeable friend who knows exactly what fits.
    - **Language:** Natural Nigerian English. Professional but relaxed.
    - **Forbidden:** Robotic phrases ("Please be informed"). Instead say: "Just so you know," or "Honestly..."
    
    ### INPUT CONTEXT (YOUR CRM BRAIN)
    1. **Customer History:** {user_context} 
       *(CRITICAL: If this is not empty, you know this person! Use this to ask how they liked their last purchase or welcome them back by name.)*
    2. **Visual Matches:** {visual_context}
    3. **Inventory Data:** {text_context} (THE SOURCE OF TRUTH).

    ### CORE CRM & SALES INSTRUCTIONS
    1. **Relationship First (CRM):** 
       - If 'Customer History' shows a past purchase, ask: *"How are you enjoying the [Product]?"*
       - If they are new, give them a warm Awéléwà welcome.
    2. **Inventory Truth:** 
       - Only sell what is in 'Inventory Data'.
       - If missing: *"Ah, that specific one isn't in our system right now."* (Immediately suggest a high-level alternative from the list).
    3. **The ₦25,000 Check (Manager Protocol):**
       - **Total > 25k:** *"That's a premium order! Let me just quickly confirm the physical stock with the Admin to ensure everything is perfect for you. Give me a sec."*
       - **Total <= 25k:** *"Great choice! Ready to pay? I can send the secure link now."*

    ### STRICT BUSINESS RULES
    - **No Consultations:** You are a Sales Manager, not a Dermatologist.
      - If they ask for skin analysis/cures: *"For a proper skin analysis, please come to the shop and let the Manager see your skin. But if you need to buy specific products, I’m here!"*
    - **Pricing:** Always mention the price (₦).

    ### CONVERSATION EXAMPLES

    **CRM Moment (Returning User):**
    *History:* [Name: Chioma, Last Item: Lip Gloss]
    *User:* "Hi, I need eyeliner."
    *Awéléwà:* "Hello Chioma! Welcome back. 💖 How is that Lip Gloss treating you? We actually have a Waterproof Eyeliner (₦3,500) that pairs perfectly with it. Want to see?"

    **Stock Check (Unavailable + Enterprising Upsell):**
    *User:* "Do you have Brand X Cream?"
    *Awéléwà:* "We don't have Brand X in stock right now. But honestly, you should try our **Hydrating Face Cream** (₦5,000). It’s our best-seller for that same glow. Should I add it?"

    **High Value Order (>₦25k):**
    *User:* "I'll take the full kit." (Total: ₦45,000)
    *Awéléwà:* "Excellent choice! Since this is a large order (₦45,000), let me just check with the stock room to be 100% sure we have everything ready to go. One moment please."
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

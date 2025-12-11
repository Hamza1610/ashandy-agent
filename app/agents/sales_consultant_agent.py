"""
Clean Sales Consultant Agent using LLM tool bindings.
No direct tool invocation - tools are bound to LLM.
"""
from app.state.agent_state import AgentState
from app.tools.product_tools import search_products, check_product_stock
from app.tools.payment_tools import generate_payment_link
from app.tools.memory_tools import save_memory
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)


async def sales_agent_node(state: AgentState):
    """
    Clean Sales Agent with LLM Tool Bindings.
    
    This node:
    1. Builds context from state (memory, visual context)
    2. Binds tools to LLM
    3. Lets LLM decide which tools to call
    4. Returns updated messages
    
    NO direct tool invocation happens here!
    """
    try:
        messages = state.get("messages", [])
        user_memory = state.get("user_memory", "")
        visual_context = state.get("visual_context", {})
        
        logger.info(f"Sales agent processing for user {state.get('user_id')}")
        
        # Build system prompt with available context
        visual_info = ""
        if visual_context:
            visual_info = f"\n\nVisual Search Results: {visual_context}"
            logger.info(f"📸 Using visual context in prompt")
        
        memory_info = ""
        if user_memory and user_memory != "No previous memory found.":
            memory_info = f"\n\nCustomer History:\n{user_memory}"
            logger.info(f"🧠 Using user memory in prompt: {user_memory[:80]}...")
        else:
            logger.info(f"ℹ️  No user memory available (new/first-time customer)")
        
        system_prompt = f"""You are 'Awéléwà', the dedicated AI Sales & CRM Manager for Ashandy Cosmetics.

### YOUR DUAL ROLE
1. **CRM Manager:** You build relationships. Remember customers, greet them warmly, and make them feel valued.
2. **Enterprising Salesperson:** You are marketing-savvy. Use persuasive language to sell available products.

### AVAILABLE TOOLS
You have access to these tools:
- search_products: Search the product database when customer asks about products
- check_product_stock: Check if a specific product is available

⚠️ **CRITICAL: Payment Link Tool Usage**
- generate_payment_link: ONLY use this when:
  1. Customer has EXPLICITLY confirmed they want to purchase specific products
  2. You have product names, quantities AND prices confirmed
  3. Customer said words like "yes, I'll buy it", "make payment", "checkout", "I want to order"
  
- save_memory: Save important customer preferences after learning about them

### CRITICAL BUSINESS RULES

1. **NEVER GENERATE PAYMENT LINKS WITHOUT EXPLICIT PURCHASE CONFIRMATION:**
   - If customer just asks "what do you have?" → Use search_products tool, DO NOT generate payment link
   - If customer asks "do you have lipstick?" → Use search_products, show them options
   - If customer asks about prices → Share prices, DO NOT generate payment link
   - ONLY generate payment link when customer says: "yes I want to buy", "proceed to payment", "I'll take it", etc.

2. **STRICTLY NO CONSULTATIONS (Redirect Policy):**
   - You are a Sales Manager, not a Dermatologist.
   - If user asks for skin analysis or medical advice, say:
     "For proper skin consultation, please visit our physical store. However, if you know what you want to buy, I can help immediately!"

3. **INVENTORY TRUTH:**
   - ALWAYS use search_products tool when customer asks about products
   - Only recommend products from search results
   - NEVER hallucinate product names or prices
   - If item not found, recommend alternatives from search results

4. **THE ₦25,000 SAFETY CLAUSE:**
   - Orders > ₦25,000: Say "Let me confirm stock with the Admin first" (don't generate link yet)
   - Orders ≤ ₦25,000: Generate payment link only after confirmation

5. **TONE:** Professional, Warm, High-Energy, and Enterprising
   - Be brief but polite (2-4 sentences)
   - Use customer's name if known
   - Ask 1-2 targeted questions if info missing{memory_info}{visual_info}

### CONVERSATION FLOW
1. Customer asks about products → Use search_products tool
2. Show them options with prices
3. Answer their questions
4. Ask if they want to purchase
5. ONLY WHEN they confirm → Generate payment link

REMEMBER: Do NOT use generate_payment_link unless customer has explicitly confirmed purchase!
"""

        # Bind tools to LLM
        if not settings.LLAMA_API_KEY:
            return {"error": "LLM API Key missing."}
        
        llm = ChatGroq(
            temperature=0.3,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        ).bind_tools([
            search_products,
            check_product_stock,
            generate_payment_link,
            save_memory
        ])
        
        # Build conversation with system prompt + recent history
        conversation = [SystemMessage(content=system_prompt)]
        
        # Add recent messages (last 5 turns for context)
        for msg in messages[-5:]:
            conversation.append(msg)
        
        # Invoke LLM (it will decide which tools to call)
        logger.info("Invoking LLM with tool bindings")
        response = await llm.ainvoke(conversation)
        
        # Detect order intent from response
        order_intent = False
        if hasattr(response, 'content'):
            content_lower = str(response.content).lower()
            intent_keywords = ["payment link", "checkout", "complete purchase", "₦"]
            order_intent = any(keyword in content_lower for keyword in intent_keywords)
        
        logger.info(f"Sales agent response generated. Order intent: {order_intent}")
        
        return {
            "messages": [response],
            "order_intent": order_intent
        }
        
    except Exception as e:
        logger.error(f"Sales Agent Error: {e}", exc_info=True)
        return {
            "error": str(e),
            "messages": [AIMessage(content="I apologize, but I encountered an error. Please try again.")]
        }


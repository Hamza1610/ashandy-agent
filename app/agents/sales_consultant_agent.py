"""
Clean Sales Consultant Agent using LLM tool bindings.
No direct tool invocation - tools are bound to LLM.
"""
from app.state.agent_state import AgentState
from app.tools.product_tools import search_products, check_product_stock
from app.tools.simple_payment_tools import request_payment_link  # Simple tool for sales agent
from app.tools.email_tools import request_customer_email  # Email collection before payment
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
        
        logger.info(f"🎯 SALES AGENT CALLED for user {state.get('user_id')}")
        logger.info(f"📥 Sales agent received {len(messages)} messages")
        
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

### WHATSAPP FORMATTING (IMPORTANT)
Format responses for easy reading:
- Use *bold* for product names: *Product Name*
- Add emojis sparingly: ✨ 💄 🛍️
- Keep messages brief (2-3 paragraphs max)
- List products clearly: *RINGLIGHT* - ₦10,000 (18 in stock)
- Always end with a clear call-to-action

### AVAILABLE TOOLS
You have access to these tools:
- search_products: Search the product database when customer asks about products
- check_product_stock: Check if a specific product is available

⚠️ **CRITICAL: Payment Link Tool Usage**
- request_payment_link: ONLY use this when:
  1. Customer has EXPLICITLY confirmed they want to purchase specific products
  2. You know the product names and total amount
  3. Customer said words like "yes, I'll buy it", "make payment", "checkout", "I want to order"
  
- save_memory: Save important customer preferences after learning about them

### CRITICAL BUSINESS RULES

1. **NEVER REQUEST PAYMENT LINKS WITHOUT EXPLICIT PURCHASE CONFIRMATION:**
   - If customer just asks "what do you have?" → Use search_products tool, DO NOT request payment
   - If customer asks "do you have lipstick?" → Use search_products, show them options
   - If customer asks about prices → Share prices, DO NOT request payment
   - ONLY request payment when customer says: "yes I want to buy", "proceed to payment", "I'll take it", etc.

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

### PAYMENT & ORDER FLOW (FOLLOW EXACTLY)

**When customer wants to buy** (says "I want", "I'll take it", "checkout"):

**STEP 1: Check for Email**
- If NO email → Call `request_customer_email` tool
- Say: "Great! I need your email for payment confirmation. What's your email?"
- **WAIT** for customer to provide email in next message

**STEP 2: Request Payment (only after email received)**
- Call `request_payment_link` with:
  - `product_names`: **ONLY** what customer chose (e.g., "100% MINK LASH 20 PAIRS")
  - `total_amount`: **ONLY** price of chosen item (e.g., 8000)

**CRITICAL RULES:**
❌ DO NOT include ALL products mentioned in chat
❌ DO NOT include products customer only browsed
✅ ONLY products customer said "I want" or "I'll buy"
✅ Example: Customer chose mink lash → request payment for ONLY mink lash, not ringlight they asked about earlier

**STEP 3: After Calling request_payment_link**
- Say: "Perfect! Payment link sent. Complete payment to confirm order."
- **STOP** - Do not continue conversation
- Payment system takes over from here
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
            request_customer_email,  # Ask for email before payment
            request_payment_link,  # Simple payment request tool
            save_memory
        ])
        
        # Build conversation with system prompt + recent history
        conversation = [SystemMessage(content=system_prompt)]
        
        # Add recent messages (last 5 turns for context)
        for msg in messages[-5:]:
            conversation.append(msg)
        
        # Invoke LLM (it will decide which tools to call)
        print(f"\n>>> SALES AGENT: Invoking LLM for {state.get('user_id')}")
        print(f">>> SALES AGENT: Conversation has {len(conversation)} messages")
        
        response = await llm.ainvoke(conversation)
        
        print(f"\n>>> SALES AGENT: LLM Response received")
        print(f">>> SALES AGENT: Response type: {type(response).__name__}")
        print(f">>> SALES AGENT: Response content: '{response.content[:200] if hasattr(response, 'content') and response.content else 'EMPTY/NONE'}'")
        print(f">>> SALES AGENT: Has tool_calls: {bool(hasattr(response, 'tool_calls') and response.tool_calls)}")
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f">>> SALES AGENT: Tool calls: {[tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown') for tc in response.tool_calls]}")
        
        logger.info(f"✅ LLM responded. Type: {type(response).__name__}")
        logger.info(f"📤 Response content: '{response.content[:150] if hasattr(response, 'content') else 'NO CONTENT'}...'")
        logger.info(f"🔧 Has tool_calls: {bool(hasattr(response, 'tool_calls') and response.tool_calls)}")
        
        # Detect order intent from response - check if payment link was generated
        order_intent = False
        
        # Check if generate_payment_link tool was called
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                if 'payment_link' in tool_name.lower():
                    order_intent = True
                    print(f"\n>>> SALES AGENT: Payment link tool detected! Order intent = True")
                    break
        
        # Also check content for payment-related keywords
        if not order_intent and hasattr(response, 'content') and response.content:
            content_lower = str(response.content).lower()
            intent_keywords = ["payment link", "checkout", "complete purchase", "here is your payment"]
            order_intent = any(keyword in content_lower for keyword in intent_keywords)
        
        print(f"\n>>> SALES AGENT: Returning response to graph")
        print(f">>> SALES AGENT: Order intent: {order_intent}")
        
        logger.info(f"✅ Sales agent response generated. Order intent: {order_intent}")
        logger.info(f"📨 Returning response to graph: messages=[{type(response).__name__}], order_intent={order_intent}")
        
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


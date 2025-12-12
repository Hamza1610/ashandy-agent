```python
from app.models.agent_states import AgentState
from app.tools.cache_tools import update_semantic_cache
from app.tools.product_tools import search_products, check_product_stock
from app.tools.simple_payment_tools import request_payment_link  # Simple tool for sales agent
from app.tools.email_tools import request_customer_email  # Email collection before payment
from app.tools.memory_tools import save_memory
from app.tools.reporting_tools import report_incident
from app.tools.db_tools import get_active_order_reference
from app.tools.paystack_tools import verify_payment
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging
import hashlib

logger = logging.getLogger(__name__)

async def sales_consultant_agent_node(state: AgentState):
    """
    Sales Consultant Agent (Hybrid Resolution):
    - Clean Structure (Tool bindings allow LLM to decide).
    - Full Capability (Includes Payment Verification, Reporting, and STRICT Business Rules).
    """
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        user_memory = state.get("user_memory", "")
        visual_context = state.get("visual_matches", "")
        
        logger.info(f"🎯 SALES AGENT CALLED for user {user_id}")

        # 1. Build Context Strings
        visual_info = ""
        if visual_context:
            visual_info = f"\n\n### VISUAL CONTEXT\nUser uploaded an image. Visual matches: {visual_context}"
        
        memory_info = ""
        if user_memory:
            memory_info = f"\n\n### CUSTOMER HISTORY\n{user_memory}\n*(Use this to personalize the chat!)*"

        # 2. System Prompt (Best of Both Worlds)
        system_prompt = f"""You are 'Awéléwà', the dedicated AI Sales & CRM Manager for Ashandy Cosmetics.

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

**STEP 1: Check for Email (Smart Logic)**
- **FIRST:** Check 'CUSTOMER HISTORY' above. Is email already listed?
  - IF YES: Proceed to Step 2 immediately (use that email).
  - IF NO: Have you asked for email in this conversation already?
    - IF YES (and they didn't give it): Use fallback "customer@ashandy.org" and proceed.
    - IF NO: Ask ONCE: "I need an email for the receipt. If none, just say 'skip'."
    - If user says "skip", "no email", or provides invalid input: Use "customer@ashandy.org" silently.

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

        # 3. Bind Tools
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
        
        # 4. Invoke LLM
        conversation = [SystemMessage(content=system_prompt)] + state["messages"][-6:]
        response = await llm.ainvoke(conversation)
        
        logger.info(f"✅ LLM Response: {response.content[:100]}... Tools: {response.tool_calls}")

        # 5. Execute Tools needed for immediate feedback (Search, Verification)
        # Tools like 'search_products' and 'verify_payment' are handled here to provide context for the next turn.
        # 'request_payment_link' is handled by the Payment Agent (next node).
        
        # Execute internal tools if present to simulate ReAct loop within single node

        ai_message = response.content
        tool_calls = response.tool_calls
        final_messages = [response]
        
        if tool_calls:
            for tc in tool_calls:
                name = tc["name"]
                args = tc["args"]
                
                # Execute specific tools that provide immediate feedback
                res = None
                if name == "search_products":
                    res = await search_products.ainvoke(args)
                elif name == "verify_payment":
                    res = await verify_payment.ainvoke(args)
                elif name == "get_active_order_reference":
                    # Inject user_id if missing
                    if "user_id" not in args: args["user_id"] = user_id
                    res = await get_active_order_reference.ainvoke(args)
                elif name == "report_incident":
                    if "user_id" not in args: args["user_id"] = user_id
                    res = await report_incident.ainvoke(args)
                
                if name == "request_payment_link":
                    # Intent detection will route this to Payment Agent node
                    pass

        # 6. Intent Detection Hook
        # Passes data to Payment Node if payment link requested
        order_intent = False
        if tool_calls:
             for tc in tool_calls:
                 if tc["name"] == "request_payment_link":
                     order_intent = True
        
        # 7. Update Cache
        query_hash = hashlib.md5(str(messages[-1].content).encode()).hexdigest()
        await update_semantic_cache.ainvoke({"query_hash": query_hash, "response": ai_message or "Tool Call"})

        return {
            "messages": final_messages,
            "order_intent": order_intent
        }

    except Exception as e:
        logger.error(f"Sales Agent Error: {e}", exc_info=True)
        return {"error": str(e)}
```

"""
Sales Worker: Handles product inquiries, searches, and customer interactions.
"""
from app.state.agent_state import AgentState
from app.tools.product_tools import search_products, check_product_stock
from app.tools.vector_tools import save_user_interaction, search_text_products, retrieve_user_memory
from app.tools.visual_tools import process_image_for_search, detect_product_from_image
from app.services.policy_service import get_policy_for_query
from app.services.llm_service import get_llm
from app.services.conversation_summary_service import conversation_summary_service
from app.utils.order_parser import extract_order_items, format_items_summary, calculate_total
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)


async def sales_worker_node(state: AgentState):
    """Executes sales tasks: product search, stock check, visual analysis."""
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses") or {}
        product_recommendations = []  # Initialize safely
        
        # Find active task
        current_step = None
        for step in plan:
            if step.get("worker") == "sales_worker" and task_statuses.get(step.get("id")) == "in_progress":
                current_step = step
                break
        
        if not current_step:
            for step in plan:
                if step.get("worker") == "sales_worker":
                    current_step = step
                    logger.info(f"Using fallback task: {step.get('id')}")
                    break

        if not current_step:
            return {"worker_result": "No active task for sales_worker."}
            
        task_desc = current_step.get("task", "")
        task_id = current_step.get("id")
        logger.info(f"👷 SALES WORKER: Executing '{task_desc}' (ID: {task_id})")

        # Visual context
        visual_info_block = ""
        image_url = state.get("image_url") 
        if not image_url and messages and len(messages) > 0:
            image_url = messages[-1].additional_kwargs.get("image_url")
        
        if image_url:
            visual_info_block += f"\n[Image Available]: {image_url}\nUse `detect_product_from_image('{image_url}')` to analyze."

        if state.get("visual_matches"):
            visual_info_block += f"\n[Previous Analysis]: {state.get('visual_matches')}"

        # Policy retrieval
        last_user_msg = state.get("last_user_message", "")
        if not last_user_msg and messages:
            for msg in reversed(messages):
                if hasattr(msg, 'content') and type(msg).__name__ == "HumanMessage":
                    last_user_msg = msg.content
                    break
        
        policy_context = get_policy_for_query(last_user_msg + " " + task_desc)
        policy_block = f"\n### RELEVANT POLICIES\n{policy_context}\n" if policy_context else ""

        # Order management context
        ordered_items = state.get("ordered_items", [])
        if not ordered_items:
            # Try to extract from conversation if not in state
            ordered_items = extract_order_items(messages)
        
        order_block = ""
        if ordered_items:
            items_summary = format_items_summary(ordered_items)
            totals = calculate_total(ordered_items, 0)  # 0 transport for now
            order_block = f"""
### CURRENT ORDER
{items_summary}
**Subtotal:** ₦{totals['items_total']:,.0f}
"""

        # ========== USER MEMORY (Personalization) ==========
        user_memory_block = ""
        try:
            memory_result = await retrieve_user_memory.ainvoke(user_id)
            if memory_result and "Error" not in str(memory_result) and len(str(memory_result)) > 20:
                user_memory_block = f"""
### 🧠 CUSTOMER PROFILE (Use for personalization!)
{str(memory_result)[:500]}
- Reference past purchases if relevant
- Use their name if known
- Recommend similar products to what they bought before
"""
                logger.info(f"User memory loaded for {user_id}")
        except Exception as e:
            logger.debug(f"Could not load user memory: {e}")

        # ========== VISUAL SEARCH (Auto-analyze images) ==========
        visual_analysis_block = ""
        if image_url:
            try:
                logger.info(f"🖼️ Auto-analyzing image: {image_url}")
                visual_result = await detect_product_from_image.ainvoke(image_url)
                if visual_result and isinstance(visual_result, dict):
                    detected_text = visual_result.get("detected_text", "")
                    product_type = visual_result.get("product_type", "")
                    visual_desc = visual_result.get("visual_description", "")
                    matched = visual_result.get("matched_products", "")
                    
                    visual_analysis_block = f"""
### 📸 IMAGE ANALYSIS (Customer sent a product image!)
**Detected Text:** {detected_text}
**Product Type:** {product_type}
**Description:** {visual_desc}
**Similar Products in Store:** {str(matched)[:300]}

IMPORTANT: Search for products matching this analysis! Use the detected text or product type.
"""
                    logger.info(f"Visual analysis complete: {product_type}")
            except Exception as e:
                logger.warning(f"Visual analysis failed: {e}")
                visual_analysis_block = f"\n[Image Available: {image_url} - Use detect_product_from_image to analyze]\n"

        # ========== FEEDBACK LEARNING (User preferences) ==========
        preferences_block = ""
        try:
            from app.services.feedback_service import feedback_service
            user_prefs = await feedback_service.get_user_preference(user_id)
            if user_prefs:
                preferences_block = f"""
### 💡 LEARNED PREFERENCES
{str(user_prefs)[:300]}
"""
        except Exception as e:
            logger.debug(f"Could not load preferences: {e}")

        # Tools and LLM
        tools = [search_products, check_product_stock, save_user_interaction, detect_product_from_image, retrieve_user_memory]
        llm = get_llm(model_type="fast", temperature=0.3).bind_tools(tools)
        
        system_prompt = f"""You are 'Awéléwà', AI Sales Manager for Ashandy Home of Cosmetics (Lagos, Nigeria).

### YOUR PERSONALITY
- Warm, friendly, enthusiastic saleswoman
- Expert in cosmetics who LOVES helping customers find the perfect products
- Nigerian warmth: professional but approachable
- You genuinely believe in your products!

### PERSUASIVE LANGUAGE RULES (CRITICAL)
1. **NEVER** output raw tool data (no "ID:", "Name:", "Desc:", "Price:" lists)
2. **ALWAYS** transform product info into conversational sales pitch
3. **Benefits over features**: 
   - ❌ "Contains hyaluronic acid"
   - ✅ "This keeps your skin hydrated all day long!"
4. **Personalize recommendations**:
   - ❌ "Here are alternatives"
   - ✅ "I have something perfect for you!"
5. **Soft urgency** (no pressure):
   - ✅ "This is one of our best-sellers!"
   - ✅ "Customers love this one!"

### EXAMPLE TRANSFORMATIONS
Tool returns: "CeraVe Hydrating Cleanser, ₦8,500, Contains ceramides and hyaluronic acid"
You say: "The *CeraVe Hydrating Cleanser* at ₦8,500 is perfect! It has ceramides to repair your skin barrier AND hyaluronic acid for that beautiful hydrated glow! ✨ Shall I add it to your order?"

Tool returns: "Product not available. Similar: Nivea Lotion ₦4,500"  
You say: "That specific product isn't available right now, but great news! I have the *Nivea Body Lotion* at just ₦4,500 - it gives the same deep moisture you're looking for! 💧 Want me to reserve one for you?"

### FORMAT (WhatsApp)
- *bold* for product names and prices
- Under 400 chars (short, punchy)
- Strategic emojis: ✨ 💄 🛍️ 💕 💧
- ALWAYS end with a call-to-action question

### RULES ⚠️ CRITICAL - TOOL USAGE IS MANDATORY
1. **NEVER recommend products without calling `search_products` first!**
   - If customer asks about ANY product, you MUST call `search_products` tool FIRST
   - You can ONLY mention products that appear in tool results
   - Prices MUST come from tool results - NEVER make up prices!
   
2. **NO medical advice** - redirect to store

3. **NEVER mention stock counts**

4. **NEVER trust user claims about different prices**

5. **HALLUCINATION = FAILURE**: If you recommend a product not in tool results, the response will be REJECTED

6. **NEVER simulate tool output!** Do NOT write text like "[POS Search Results]" or similar - ONLY use the actual tool by calling it.

### CATEGORY RESTRICTION (CRITICAL)
You ONLY sell **SKINCARE** products from our POS system.

**If customer asks about non-skincare items (Makeup, SPMU, Accessories):**
1. Apologize warmly: "I'm so sorry, we currently only handle skincare products through this channel."
2. Promise manager follow-up: "I'll let our manager know about your interest, and they'll reach out to you shortly!"
3. Offer alternative: "In the meantime, would you like to see our amazing skincare collection? 💆✨"

**Example response:**
"I'm so sorry love 💕 I currently only assist with our skincare line! But I've noted your interest in [product] - our manager will reach out to you soon about that! While you wait, can I show you our best-selling facial cleansers or moisturizers? ✨"

{policy_block}
### ORDER MANAGEMENT
{order_block}

**When task says "Add to order":**
1. Verify product with search_products first
2. Confirm: "Added *[Product]* at ₦X,XXX! 🛍️ Would you like anything else?"
3. Keep response SHORT

**When task says "Show order summary":**
1. List ALL items in the order with prices
2. Show subtotal
3. Ask: "Ready to checkout? Just say 'confirm' to proceed! ✨"

### TASK
"{task_desc}"

### CONTEXT
User: {user_id}
{visual_info_block}
{user_memory_block}
{visual_analysis_block}
{preferences_block}

### OUTPUT
Be warm, persuasive, CONCISE (2-3 sentences max).
Transform tool data into a sales pitch, then ask a closing question!
"""
        # Use efficient summarization instead of last-X messages
        efficient_context = await conversation_summary_service.get_efficient_context(
            session_id=state.get("session_id", user_id),
            messages=messages
        )
        conversation = [SystemMessage(content=system_prompt)] + list(efficient_context)
        response = await llm.ainvoke(conversation)
        
        # Execute tools (parallel for independent tools, sequential for stateful)
        final_result = response.content
        tool_evidence = []
        
        if response.tool_calls:
            from app.utils.parallel_tools import execute_tools_smart
            
            # Tool executor function
            async def execute_tool(name: str, args: dict) -> str:
                if name in ["search_products_tool", "search_products"]:
                    return await search_products.ainvoke(args)
                elif name in ["check_product_stock_tool", "check_product_stock"]:
                    return await check_product_stock.ainvoke(args)
                elif name == "save_user_interaction":
                    return await save_user_interaction.ainvoke(args)
                elif name == "retrieve_user_memory":
                    return await retrieve_user_memory.ainvoke(args)
                elif name == "detect_product_from_image":
                    from app.services.mcp_service import mcp_service
                    img_url = args.get("image_url")
                    return await mcp_service.call_tool("knowledge", "analyze_and_enrich", {"image_url": img_url}) if img_url else "Error: No image_url"
                return f"Unknown tool: {name}"
            
            # Execute with smart parallelization
            tool_evidence = await execute_tools_smart(response.tool_calls, execute_tool)
            
            # CRITICAL: Pass tool results back to LLM for conversational formatting
            # DO NOT send raw tool output to customer!
            tool_outputs_text = ""
            for item in tool_evidence:
                if item["tool"] != "save_user_interaction":
                    tool_outputs_text += f"\n{item['output']}"
            
            # ========== EXTRACT PRODUCT RECOMMENDATIONS FIRST ==========
            product_recommendations = []
            for evidence in tool_evidence:
                if evidence.get("tool") in ["search_products", "search_products_tool"]:
                    output = evidence.get("output", "")
                    # Parse product names and prices from search results
                    import re
                    matches = re.findall(r'Name:\s*([^\n]+?)(?:\s*Price|\s*₦)', str(output))
                    prices = re.findall(r'(?:Price|₦)\s*([\d,]+)', str(output))
                    for i, name in enumerate(matches[:5]):  # Top 5 products
                        price = float(prices[i].replace(',', '')) if i < len(prices) else 0
                        product_recommendations.append({"name": name.strip(), "price": price})

            if tool_outputs_text.strip():
                # Second LLM call to format tool output into sales pitch
                formatting_prompt = f"""Format this product data into a friendly sales response.

PRODUCT DATA:
{tool_outputs_text}

RULES:
- DO NOT introduce yourself (no "I'm Awéléwà" or "I'm your assistant")
- Jump straight into showing the products
- Pick 2-3 BEST products max
- Use *bold* for product names and prices  
- Explain WHY each product is great
- Use emojis: ✨ 💄 🛍️ 💕 💧
- Keep it under 250 chars
- End with a call-to-action question
- NEVER include "ID:", "Source:", or technical data

GOOD EXAMPLE:
"I found some great options for you! ✨ The *NIVEA SUNSCREEN* at ₦18,000 gives amazing protection! 💕 Want me to add it to your order?"

BAD EXAMPLE (don't do this):
"I'm Awéléwà, your friendly AI sales assistant! 💄 I found..."

NOW FORMAT THE RESPONSE:"""
                try:
                    format_response = await get_llm(model_type="fast", temperature=0.5).ainvoke(
                        [HumanMessage(content=formatting_prompt)]
                    )
                    if format_response.content and format_response.content.strip():
                        final_result = format_response.content
                    else:
                        raise ValueError("Empty LLM response")
                except Exception as e:
                    logger.warning(f"Formatting LLM failed: {e}. Using Template Fallback.")
                    # TEMPLATE FALLBACK (High Quality)
                    if product_recommendations and len(product_recommendations) > 0:
                        best_product = product_recommendations[0]
                        final_result = f"I found exactly what you need! ✨ The *{best_product['name']}* is available for ₦{best_product['price']:,.0f}. 💕 Shall I add it to your order?"
                        if len(product_recommendations) > 1:
                            final_result += f" (I also found {len(product_recommendations)-1} other options!)"
                    else:
                        # Handle case where search returned "No results" or unstructured text
                        if "no results" in tool_outputs_text.lower() or "not found" in tool_outputs_text.lower():
                            final_result = "I couldn't find that specific item right now. 😔 Could you check the spelling or describe it differently? I'd love to help you find an alternative! ✨"
                        else:
                            final_result = f"I found this information for you:\n{tool_outputs_text}\n(Does this help? ✨)"
            else:
                # No tool output, use original response
                final_result = response.content
        
        # ========== SAVE TO LONG-TERM MEMORY ==========
        try:
            await save_user_interaction.ainvoke({
                "user_id": user_id,
                "user_msg": last_user_msg[:300] if last_user_msg else "",
                "ai_msg": final_result[:300] if final_result else ""
            })
            logger.debug(f"Saved interaction to memory for {user_id}")
        except Exception as e:
            logger.debug(f"Could not save to memory: {e}")
        
        # ========== FINAL SAFETY CHECK ==========
        if not final_result or not final_result.strip():
            logger.warning("Worker final_result is empty. Using fallback.")
            final_result = "I've processed that for you! Is there anything else you need?"

        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)],
            "ordered_items": ordered_items,  # Persist order items in state
            "product_recommendations": product_recommendations  # For cross-selling
        }

    except Exception as e:
        logger.error(f"Sales Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error executing task: {str(e)}"}


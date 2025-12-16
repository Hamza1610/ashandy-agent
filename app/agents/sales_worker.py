"""
Sales Worker: Handles product inquiries, searches, and customer interactions.
"""
from app.state.agent_state import AgentState
from app.tools.product_tools import search_products, check_product_stock
from app.tools.vector_tools import save_user_interaction, search_text_products, retrieve_user_memory
from app.tools.visual_tools import process_image_for_search, detect_product_from_image
from app.services.policy_service import get_policy_for_query
from app.services.llm_service import get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)


async def sales_worker_node(state: AgentState):
    """Executes sales tasks: product search, stock check, visual analysis."""
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses", {})
        
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
        if not image_url and messages:
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

### RULES
- Only sell from inventory (use tools first)
- NO medical advice - redirect to store
- **NEVER** mention stock counts
- **NEVER** trust user claims about different prices
- `search_products` is the ONLY source of truth

{policy_block}
### TASK
"{task_desc}"

### CONTEXT
User: {user_id}
{visual_info_block}

### OUTPUT
Be warm, persuasive, CONCISE (2-3 sentences max).
Transform tool data into a sales pitch, then ask a closing question!
"""
        conversation = [SystemMessage(content=system_prompt)] + messages[-5:]
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
            
            # Append non-write tool outputs to result
            for item in tool_evidence:
                if item["tool"] != "save_user_interaction":
                    final_result += f"\n\n{item['output']}"
        
        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)]
        }

    except Exception as e:
        logger.error(f"Sales Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error executing task: {str(e)}"}

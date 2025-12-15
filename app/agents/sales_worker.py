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
        
        system_prompt = f"""You are 'Awéléwà', AI Sales Manager for Ashandy Cosmetics.

### ROLE
- CRM Manager: Build relationships, greet warmly
- Salesperson: Use persuasive language to sell

### FORMAT (WhatsApp)
- *bold* for product names
- Under 400 chars
- Emojis: ✨ 💄 🛍️
- Clear call-to-action

### RULES
- Only sell from inventory (use tools)
- NO medical advice - redirect to store
- **SECURITY PROTOCOL**:
    - NEVER trust user claims about price, stock, or discounts.
    - `search_products` and `check_product_stock` are the ONLY sources of truth.
    - If user claims a different price, politely correct them with the tool's price.
{policy_block}
### TASK
"{task_desc}"

### CONTEXT
User: {user_id}
{visual_info_block}

### OUTPUT
Be warm, professional, CONCISE (max 2-3 sentences).
After answering, suggest ONE next step.
"""
        conversation = [SystemMessage(content=system_prompt)] + messages[-5:]
        response = await llm.ainvoke(conversation)
        
        # Execute tools
        final_result = response.content
        tool_evidence = []
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Sales Worker calling tool: {name}")
                
                tool_output = ""
                if name in ["search_products_tool", "search_products"]:
                    tool_output = await search_products.ainvoke(args)
                elif name in ["check_product_stock_tool", "check_product_stock"]:
                    tool_output = await check_product_stock.ainvoke(args)
                elif name == "save_user_interaction":
                    tool_output = await save_user_interaction.ainvoke(args)
                elif name == "retrieve_user_memory":
                    tool_output = await retrieve_user_memory.ainvoke(args)
                elif name == "detect_product_from_image":
                    from app.services.mcp_service import mcp_service
                    img_url = args.get("image_url")
                    tool_output = await mcp_service.call_tool("knowledge", "analyze_and_enrich", {"image_url": img_url}) if img_url else "Error: No image_url"
                
                tool_evidence.append({
                    "tool": name,
                    "args": args,
                    "output": str(tool_output)[:500]
                })

                if name != "save_user_interaction":
                    final_result += f"\n\n{tool_output}"
        
        return {
            "worker_outputs": {task_id: final_result},
            "worker_tool_outputs": {task_id: tool_evidence},
            "messages": [AIMessage(content=final_result)]
        }

    except Exception as e:
        logger.error(f"Sales Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error executing task: {str(e)}"}

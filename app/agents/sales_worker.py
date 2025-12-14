from app.state.agent_state import AgentState
from app.tools.product_tools import search_products, check_product_stock
from app.tools.vector_tools import save_user_interaction, search_text_products, retrieve_user_memory
from app.tools.visual_tools import process_image_for_search, detect_product_from_image
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)

async def sales_worker_node(state: AgentState):
    """
    Sales Worker: The Execution Arm.
    """
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        
        # --- PUB/SUB TASK RETRIEVAL ---
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses", {})
        
        # Find My Task (Worker = sales_worker AND Status = in_progress)
        logger.info(f"DEBUG SALES WORKER: Plan Length: {len(plan)}")
        logger.info(f"DEBUG SALES WORKER: Statuses: {task_statuses}")
        
        current_step = None
        for step in plan:
            s_id = step.get("id")
            s_worker = step.get("worker")
            s_status = task_statuses.get(s_id)
            logger.info(f"Check Step {s_id}: Worker={s_worker}, Status={s_status}")
            
            if s_worker == "sales_worker" and s_status == "in_progress":
                current_step = step
                break
        
        # Fallback: If Dispatcher sent us here but status state is lost (Empty Statuses), 
        # assume the first task for this worker is the one.
             for step in plan:
                 if step.get("worker") == "sales_worker":
                     current_step = step
                     logger.info(f"Using Fail-Safe: Recovered Task {step.get('id')} from plan.")
                     break

        if not current_step:
            # DEBUG: Expose state details in the response to diagnose routing issue
            debug_details = f"PlanLen={len(plan)} Statuses={task_statuses} Steps={[s.get('id') + ':' + s.get('worker') for s in plan]}"
            logger.error(f"SALES WORKER FAIL: {debug_details}")
            return {"worker_result": f"No active task for sales_worker. Context: {debug_details}"}
            
        task_desc = current_step.get("task", "")
        task_id = current_step.get("id")
        
        logger.info(f"👷 SALES WORKER: Executing '{task_desc}' (ID: {task_id})")

        # Visual Context Handling
        visual_info_block = ""
        # Check for image URL in state or message kwargs (Planner might have put it in state, or it is in the message)
        image_url = state.get("image_url") 
        if not image_url and messages:
             image_url = messages[-1].additional_kwargs.get("image_url")
        
        if image_url:
            visual_info_block += f"\n[Image Available]: {image_url}\nTo analyze AND search for this product in our inventory, use `detect_product_from_image('{image_url}')`."

        if state.get("visual_matches"):
             visual_info_block += f"\n[Previous Analysis]: {state.get('visual_matches')}"

        # Setup Tools
        # Added retrieve_user_memory so the worker can fetch context if requested by Planner
        tools = [search_products, check_product_stock, save_user_interaction, detect_product_from_image, retrieve_user_memory]
        
        llm = ChatGroq(
            temperature=0.3,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        ).bind_tools(tools)
        
        # System Prompt - Simple & Focused
        system_prompt = f"""You are 'Awéléwà', the dedicated AI Sales & CRM Manager for Ashandy Cosmetics. To customers, you are their Sales Assistant and Customer Support. 

### YOUR DUAL ROLE
1. **CRM Manager:** You build relationships. Remember customers, greet them warmly, and make them feel valued.
2. **Enterprising Salesperson:** You are marketing-savvy. Use persuasive language to sell available products.

### WHATSAPP FORMATTING (IMPORTANT)
Format responses for easy reading:
- Use *bold* for product names: *Product Name*
- Responses should be in a single message. The only exception is when it is absolutely necessary to add one more sentence for excellence.
- Add emojis sparingly: ✨ 💄 🛍️
- Always end with a clear call-to-action

### STRICTLY NO CONSULTATIONS (Redirect Policy)
You are a Sales Manager, not a Dermatologist.
If user asks for skin analysis or medical advice, say:
"For proper skin consultation, please visit our physical store. However, if you know what you want to buy, I can help immediately!"

### Inventory Truth & Alternatives
- Only sell what is in 'Inventory Data'.
- If a requested product is missing, you may suggest a **High-Level Alternative** ONLY based on product category (e.g., "We have another Toner"), NOT based on a medical cure.
- *Correct Upsell:* "We don't have Brand X, but our Brand Y Toner is very popular."
- *Incorrect Upsell (Forbidden):* "We don't have Brand X, but Brand Y will cure your acne."

### YOUR CURRENT TASK
"{task_desc}"

### YOUR GOAL
Execute this task using tools if needed, or reply to the user.
Do not worry about overall flow (payments, approvals), just do this task.
Be warm, professional, and concise.

**Context:**
User ID: {user_id}
{visual_info_block}

**Output:**
If you use a tool, the system will handle execution. 
If you simply reply, that is the result.

**Style Rules:**
- Do NOT greet the user again if you have already greeted them.
- Be conversational but efficient.
- **POLICY:** You CAN recommend products and explain their benefits/ingredients (Sales Advice).
- **CRITICAL:** Do NOT diagnose skin conditions or prescribe treatments based on symptoms (Medical Consultation). If a user asks for a diagnosis, refer them to the shop manager.
"""
        # We pass the full history so the worker has context, but emphasize the CURRENT TASK
        conversation = [SystemMessage(content=system_prompt)] + messages[-5:]
        
        response = await llm.ainvoke(conversation)
        
        # Execute Tools Manually (ReAct Style) to return a final string result
        # In a Worker node, we usually want to resolve the Action to a Result
        final_result = response.content
        tool_evidence = []
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Sales Worker calling tool: {name}")
                
                tool_output = ""
                # MATCH THE TOOL NAMES FROM DECORATORS
                if name == "search_products_tool" or name == "search_products":
                    tool_output = await search_products.ainvoke(args)
                elif name == "check_product_stock_tool" or name == "check_product_stock":
                    tool_output = await check_product_stock.ainvoke(args)
                elif name == "save_user_interaction":
                    tool_output = await save_user_interaction.ainvoke(args)
                elif name == "retrieve_user_memory":
                    tool_output = await retrieve_user_memory.ainvoke(args)
                elif name == "detect_product_from_image":
                    from app.services.mcp_service import mcp_service
                    img_url = args.get("image_url")
                    if img_url:
                        tool_output = await mcp_service.call_tool("knowledge", "analyze_and_enrich", {"image_url": img_url})
                    else:
                        tool_output = "Error: No image_url provided."
                
                # CAPTURE EVIDENCE (New for Reviewer)
                tool_evidence.append({
                    "tool": name,
                    "args": args,
                    "output": str(tool_output)[:500] # Truncate heavily for token efficiency
                })

                # Append tool output to result, UNLESS it's a silent tool like save_memory/save_interaction
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

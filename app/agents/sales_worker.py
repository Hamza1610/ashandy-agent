from app.models.agent_states import AgentState
from app.tools.product_tools import search_products, check_product_stock
from app.tools.memory_tools import save_memory
from app.tools.visual_tools import process_image_for_search, detect_product_from_image
from app.tools.vector_tools import search_text_products
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)

async def sales_worker_node(state: AgentState):
    """
    Sales Worker: The Execution Arm.
    
    Responsibilities:
    1. Executing specific tasks found in 'current_task'.
    2. Using tools (Search, Stock Check, Visual Search) to get results.
    3. Generating friendly responses based on results.
    
    Inputs: 
    - state['plan'][state['current_step_index']]
    
    Outputs:
    - worker_result: Result of the action.
    """
    try:
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        
        # Get Current Task
        plan = state.get("plan", [])
        idx = state.get("current_step_index", 0)
        
        if idx >= len(plan):
            return {"worker_result": "No more tasks."}
            
        current_step = plan[idx]
        task_desc = current_step.get("task", "")
        
        logger.info(f"👷 SALES WORKER: Executing task '{task_desc}'")

        # Visual Context Handling
        visual_info_block = ""
        # Check for image URL in state or message kwargs (Planner might have put it in state, or it is in the message)
        image_url = state.get("image_url") 
        if not image_url and messages:
             image_url = messages[-1].additional_kwargs.get("image_url")
        
        if image_url:
            visual_info_block += f"\n[Image Available]: {image_url}\nTo analyze, use `detect_product_from_image('{image_url}')`."

        if state.get("visual_matches"):
             visual_info_block += f"\n[Previous Analysis]: {state.get('visual_matches')}"

        # Setup Tools
        tools = [search_products, check_product_stock, save_memory, detect_product_from_image]
        
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
        
        if response.tool_calls:
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]
                logger.info(f"Sales Worker calling tool: {name}")
                
                tool_output = ""
                # MATCH THE TOOL NAMES FROM DECORATORS in product_tools.py
                if name == "search_products_tool" or name == "search_products":
                    tool_output = await search_products.ainvoke(args)
                elif name == "check_product_stock_tool" or name == "check_product_stock":
                    tool_output = await check_product_stock.ainvoke(args)
                elif name == "save_memory":
                    tool_output = await save_memory.ainvoke(args)
                elif name == "detect_product_from_image":
                    tool_output = await detect_product_from_image.ainvoke(args)
                
                # Append tool output to result, UNLESS it's a silent tool like save_memory
                if name != "save_memory":
                    # Clean append: Just add the content with newlines, no technical headers
                    final_result += f"\n\n{tool_output}"
        
        return {
            "worker_result": final_result
            # We do NOT increment step index here. The Planner does that on return.
        }

    except Exception as e:
        logger.error(f"Sales Worker Error: {e}", exc_info=True)
        return {"worker_result": f"Error executing task: {str(e)}"}

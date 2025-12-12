from app.models.agent_states import AgentState
from app.tools.llama_guard_tool import check_safety
from langchain_core.messages import SystemMessage
import logging

logger = logging.getLogger(__name__)

async def safety_agent_node(state: AgentState):
    """
    Safety Agent: Checks for toxic content AND strictly enforces domain relevance.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 1. Admins bypass safety checks
    if state.get("is_admin"):
        return {}
        
    user_query = last_message.content
    
    # 2. Skip check if there is no text (e.g. image-only message)
    if not user_query:
        return {} 

    # 3. Invoke Llama Guard
    # (The tool flags Off-topic or Toxic inputs)
    safety_result = await check_safety.ainvoke(user_query)
    
    # 4. Handle Blocked Messages
    if "unsafe" in safety_result.lower():
        logger.warning(f"Safety/Relevance Block triggered for: {user_query[:30]}...")
        
        return {
            "error": "Safety/Relevance violation.",
            "blocked": True, # Signal to stop the graph here
            "messages": [
                SystemMessage(content="I am Awéléwà, the CRM/Sales AI Assistant for Ashandy Cosmetics. I strictly only assist with our products, orders, and shop inquiries. I cannot discuss other topics.")
            ]
        }
        
    # 5. Message is Safe -> Pass to Sales Agent
    return {}

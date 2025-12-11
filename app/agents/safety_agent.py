from app.state.agent_state import AgentState
from app.tools.llama_guard_tool import check_safety
from langchain_core.messages import SystemMessage
import logging

logger = logging.getLogger(__name__)

async def safety_agent_node(state: AgentState):
    """
    Safety Agent: Checks for toxic content.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if state.get("is_admin"):
        # Admins bypass safety checks
        return {}
        
    user_query = last_message.content
    
    if not user_query:
        return {} # No text to check (e.g. image only)

    safety_result = await check_safety.ainvoke(user_query)
    
    if safety_result == "unsafe":
        return {
            "error": "Safety violation detected.",
            "messages": [SystemMessage(content="Your message was flagged as unsafe.")]
        }
        
    return {}

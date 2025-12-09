from app.models.agent_states import AgentState
from app.tools.pos_connector_tools import sync_inventory_from_pos
from app.tools.report_tool import generate_weekly_report
from langchain_core.messages import SystemMessage
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def admin_agent_node(state: AgentState):
    """
    Admin Agent: Handles /commands.
    """
    command = state.get("admin_command", "")
    response_text = "Command not recognized."
    
    try:
        if command.startswith("/stock"):
             # Trigger sync manually (normally this is automated via API, but admin can force it)
             # In a real scenario, this might trigger a fetch from the POS via a request
             # Here we simulate by calling the tool with dummy data or triggering the process
             response_text = "Stock sync triggered (mock)."
             
        elif command.startswith("/report"):
             date_str = datetime.now().strftime("%Y-%m-%d")
             result = await generate_weekly_report.invoke(date_str)
             response_text = result
             
        return {
            "messages": [SystemMessage(content=response_text)]
        }
        
    except Exception as e:
        logger.error(f"Admin Agent Error: {e}")
        return {"error": str(e)}

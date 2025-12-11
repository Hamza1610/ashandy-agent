from app.state.agent_state import AgentState
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
             # Real implementation: Check current stock count in DB
             from app.services.db_service import AsyncSessionLocal
             from sqlalchemy import text
             
             async with AsyncSessionLocal() as session:
                 result = await session.execute(text("SELECT COUNT(*) FROM products"))
                 count = result.scalar()
             
             response_text = f"Stock Check: {count} products found in database."
             
        elif command.startswith("/report"):
             date_str = datetime.now().strftime("%Y-%m-%d")
             result = await generate_weekly_report.ainvoke(date_str)
             response_text = result
             
        return {
            "messages": [SystemMessage(content=response_text)]
        }
        
    except Exception as e:
        logger.error(f"Admin Agent Error: {e}")
        return {"error": str(e)}

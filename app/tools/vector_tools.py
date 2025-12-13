from langchain.tools import tool
import logging
import ast

logger = logging.getLogger(__name__)

@tool
async def retrieve_user_memory(user_id: str) -> str:
    """Retrieve semantic memory/preferences for a user via Knowledge MCP."""
    logger.info(f"Retrieving memory for user_id: {user_id}")
    try:
        from app.services.mcp_service import mcp_service
        
        # Call 'search_user_context' on 'knowledge' server
        result = await mcp_service.call_tool("knowledge", "search_user_context", {
            "user_id": user_id,
            "query": f"User preferences for {user_id}"
        })
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving user memory via MCP: {e}")
        return "Error retrieving memory."

@tool
async def search_visual_products(vector: list) -> str:
    """
    Search for products using a visual embedding vector via Knowledge MCP.
    Expects vector to be a list of floats (default 768 dim for DINO).
    """
    logger.info("Executing search_visual_products via MCP")
    try:
        from app.services.mcp_service import mcp_service
        
        # Call 'search_visual_memory' on 'knowledge' server
        result = await mcp_service.call_tool("knowledge", "search_visual_memory", {"vector": vector})
        return result
        
    except Exception as e:
        logger.error(f"Error searching visual products via MCP: {e}")
        return "Error executing visual search."

@tool
async def search_text_products(query: str) -> str:
    """
    Search for products using semantic search (Knowledge Server).
    """
    logger.info(f"Executing search_text_products via MCP: '{query}'")
    try:
        from app.services.mcp_service import mcp_service
        
        # Call 'search_memory' tool on 'knowledge' server
        result = await mcp_service.call_tool("knowledge", "search_memory", {"query": query})
        return result
        
    except Exception as e:
        logger.error(f"Error searching text products via MCP: {e}")
        return "Error executing text search."

async def save_user_interaction(user_id: str, user_msg: str, ai_msg: str) -> str:
    """
    Save a chat interaction (User + AI) to long-term memory via Knowledge MCP.
    This is a normal async function (not a LangChain tool).
    """
    if not user_id or not user_msg:
        return "Missing required fields for memory save."
    
    logger.info(f"Saving interaction for user_id: {user_id} via MCP")
    try:
        from app.services.mcp_service import mcp_service
        
        text_to_save = f"User: {user_msg}\nAI: {ai_msg}"
        
        # Call 'save_interaction' on 'knowledge' server
        result = await mcp_service.call_tool("knowledge", "save_interaction", {
            "user_id": user_id,
            "text": text_to_save
        })
        return result
        
    except Exception as e:
        logger.error(f"Error saving memory via MCP: {e}", exc_info=True)
        return f"Failed to save memory: {str(e)}"

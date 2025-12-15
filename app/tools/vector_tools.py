"""
Vector Tools: Semantic search and memory management via Knowledge MCP.
"""
from langchain.tools import tool
from app.services.mcp_service import mcp_service
import logging

logger = logging.getLogger(__name__)


@tool
async def retrieve_user_memory(user_id: str) -> str:
    """Retrieve semantic memory/preferences for a user."""
    logger.info(f"Retrieving memory for: {user_id}")
    try:
        return await mcp_service.call_tool("knowledge", "search_user_context", {
            "user_id": user_id,
            "query": f"User preferences for {user_id}"
        })
    except Exception as e:
        logger.error(f"Memory retrieval error: {e}")
        return "Error retrieving memory."


@tool
async def search_visual_products(vector: list) -> str:
    """Search products using a visual embedding vector (768 dim for DINO)."""
    logger.info("Visual product search via MCP")
    try:
        return await mcp_service.call_tool("knowledge", "search_visual_memory", {"vector": vector})
    except Exception as e:
        logger.error(f"Visual search error: {e}")
        return "Error executing visual search."


@tool
async def search_text_products(query: str) -> str:
    """Search products using semantic text search."""
    logger.info(f"Text product search: '{query}'")
    try:
        return await mcp_service.call_tool("knowledge", "search_memory", {"query": query})
    except Exception as e:
        logger.error(f"Text search error: {e}")
        return "Error executing text search."


@tool
async def save_user_interaction(user_id: str, user_msg: str, ai_msg: str) -> str:
    """Save a chat interaction to long-term memory."""
    if not user_id or not user_msg:
        return "Missing required fields."
    
    logger.info(f"Saving interaction for: {user_id}")
    try:
        text_to_save = f"User: {user_msg}\nAI: {ai_msg}"
        return await mcp_service.call_tool("knowledge", "save_interaction", {
            "user_id": user_id,
            "text": text_to_save
        })
    except Exception as e:
        logger.error(f"Memory save error: {e}")
        return f"Failed to save memory: {str(e)}"

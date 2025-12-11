"""
Memory management tools for user interaction storage and retrieval.
Uses Pinecone vector store for semantic memory.
"""
from langchain.tools import tool
from app.tools.vector_tools import retrieve_user_memory, save_user_interaction
import logging

logger = logging.getLogger(__name__)


@tool("retrieve_memory_tool")
async def retrieve_memory(user_id: str) -> str:
    """
    Retrieve user's conversation history and preferences from memory.
    
    This tool fetches semantic memory about the user including:
    - Past conversations
    - Product preferences
    - Purchase history
    - Skin type, budget, etc.
    
    Args:
        user_id: The user's unique identifier
        
    Returns:
        Formatted string with user's memory context
    """
    try:
        logger.info(f"Retrieving memory for user: {user_id}")
        
        # Use existing vector tool
        memory = await retrieve_user_memory.ainvoke(user_id)
        
        if not memory or "No previous memory" in memory:
            return f"This is a new customer. No previous interaction history found."
        
        return memory
        
    except Exception as e:
        logger.error(f"Memory retrieval failed for {user_id}: {e}")
        return "Could not retrieve user history. Treating as new customer."


@tool("save_memory_tool")
async def save_memory(user_id: str, user_message: str, ai_response: str) -> str:
    """
    Save the current conversation turn to long-term memory.
    
    This stores the user's message and AI response in Pinecone
    for future context retrieval.
    
    Args:
        user_id: The user's unique identifier
        user_message: What the user said
        ai_response: How the AI responded
        
    Returns:
        Confirmation message
    """
    try:
        logger.info(f"Saving memory for user: {user_id}")
        
        # Use existing function (not a tool, so call directly)
        result = await save_user_interaction(
            user_id=user_id,
            user_msg=user_message,
            ai_msg=ai_response
        )
        
        return f"Memory saved successfully for {user_id}"
        
    except Exception as e:
        logger.error(f"Memory save failed for {user_id}: {e}")
        return f"Failed to save memory: {str(e)}"

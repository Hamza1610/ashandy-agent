from app.models.agent_states import AgentState
from app.tools.visual_tools import process_image_for_search
from app.tools.vector_tools import search_visual_products
from langchain_core.messages import SystemMessage
import logging
import json

logger = logging.getLogger(__name__)

async def visual_search_agent_node(state: AgentState):
    """
    Visual Search Agent: Processes image and finds products.
    """
    image_url = state.get("image_url")
    if not image_url:
        return {"error": "No image provided for visual search."}
        
    try:
        # 1. Generate visual embedding
        # This will call the Refactored tool using DINOv2
        embedding = await process_image_for_search.ainvoke(image_url)
        
        if not embedding:
             return {"error": "Failed to process image."}
             
        # 2. Query Pinecone using the embedding
        # This calls the Refactored vector tool
        # We assume the result is a string description of matches for now, 
        # or we could refactor tool to return list and handle formatting here.
        # The current tool returns a formatted string.
        search_results = await search_visual_products.ainvoke(embedding)
        
        # 3. Store results in state for the response node
        # We can parse the string or just carry it forward
        # Ideally, we'd structure this better, but text is fine for LLM generation later.
        
        return {
            "visual_matches": [{"description": search_results}], # Storing mostly text rep for now
            "messages": [SystemMessage(content=f"Found visual matches: {search_results}")]
        }
        
    except Exception as e:
        logger.error(f"Visual Search Agent Error: {e}")
        return {"error": f"Visual search failed: {e}"}

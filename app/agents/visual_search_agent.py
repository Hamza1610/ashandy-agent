from app.state.agent_state import AgentState
from app.tools.visual_tools import process_image_for_search, describe_image
from app.tools.vector_tools import search_visual_products, search_text_products
import logging

logger = logging.getLogger(__name__)

async def visual_search_agent_node(state: AgentState):
    """
    Visual Search Agent: Processes image -> Embeddings/Description -> Vector Search.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # We expect image_url in additional_kwargs (from webhook)
    image_url = last_message.additional_kwargs.get("image_url")
    
    logger.info(f"Visual Search Agent processing. Image URL found: {image_url}")
    
    if not image_url:
        return {"error": "No image provided."}
        
    try:
        # Strategy: Run Parallel (Visual DINO + Semantic Text)
        
        # 1. Visual Path (DINOv2)
        visual_results = ""
        embedding = await process_image_for_search.ainvoke(image_url)
        if embedding:
            visual_results = await search_visual_products.ainvoke(embedding)
            
        # 2. Semantic Path (Image -> Text -> Vector)
        # Fulfils "SAM/Extract Text" requirement
        semantic_results = ""
        description = await describe_image.ainvoke(image_url)
        if description:
            semantic_results = await search_text_products.ainvoke(description)
        
        combined_results = f"""
        Results for Image:
        [Description]: {description}
        
        {visual_results}
        
        {semantic_results}
        """
        
        # 3. Store results in state for the response node
        return {
            "visual_matches": combined_results,
            "query_type": "image" # confirm type
        }
        
    except Exception as e:
        logger.error(f"Visual Search Error: {e}")
        return {"error": "Search failed."}

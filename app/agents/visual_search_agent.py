from app.state.agent_state import AgentState
from app.tools.visual_tools import process_image_for_search, describe_image
from app.tools.vector_tools import search_visual_products, search_text_products
import logging
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

async def visual_search_agent_node(state: AgentState):
    """
    Visual Search Agent: Processes product images using dual search strategy.
    
    Strategy:
        1. DINOv2 Visual Embeddings → Vector similarity search
        2. Llama Vision Description → Semantic text search
        3. Combines results for comprehensive product matching
    
    Args:
        state: Agent state containing image_url or messages with image
        
    Returns:
        Updated state with visual search results and formatted product matches
    """
    print(f"\n>>> VISUAL AGENT: Processing image search")
    logger.info("Visual Search Agent: Starting image analysis")
    
    messages = state["messages"]
    last_message = messages[-1]
    
    # Get image URL from state (router copied it) or message kwargs
    image_url = state.get("image_url") or last_message.additional_kwargs.get("image_url")
    
    if not image_url:
        print(">>> VISUAL AGENT ERROR: No image URL found")
        logger.error("No image URL provided to visual agent")
        return {
            "messages": [AIMessage(content="Please send an image to search for products.")],
            "error": "no_image"
        }
    
    print(f">>> VISUAL AGENT: Image URL = {image_url[:80]}...")
    logger.info(f"Processing image: {image_url}")
    
    try:
        # Strategy 1:  Visual Similarity (DINOv2 Embedding)
        print(f">>> VISUAL AGENT: Generating DINOv2 embedding...")
        visual_results = ""
        embedding = await process_image_for_search.ainvoke(image_url)
        
        if embedding:
            print(f">>> VISUAL AGENT: Embedding generated ({len(embedding)} dims), searching products...")
            visual_results = await search_visual_products.ainvoke(embedding)
            print(f">>> VISUAL AGENT: Visual search complete")
        else:
            print(f">>> VISUAL AGENT WARNING: Embedding generation failed")
            logger.warning("Visual embedding failed, skipping visual search")
            
        # Strategy 2: Semantic Text Search (Llama Vision → Description → Search)
        print(f">>> VISUAL AGENT: Describing image with Llama Vision...")
        semantic_results = ""
        description = await describe_image.ainvoke(image_url)
        
        if description and "Error" not in description:
            print(f">>> VISUAL AGENT: Description = '{description[:100]}'")
            print(f">>> VISUAL AGENT: Searching products by description...")
            semantic_results = await search_text_products.ainvoke(description)
            print(f">>> VISUAL AGENT: Semantic search complete")
        else:
            print(f">>> VISUAL AGENT WARNING: Image description failed")
            logger.warning("Image description failed, skipping semantic search")
        
        # Combine results
        combined_results = f"""
Visual Search Results for Uploaded Image:

[Image Analysis]: {description or 'Could not analyze image'}

{visual_results if visual_results else '(No visual matches found)'}

{semantic_results if semantic_results else '(No semantic matches found)'}
"""
        
        print(f">>> VISUAL AGENT: Search complete, returning results")
        logger.info("Visual search completed successfully")
        
        # Return results
        return {
            "visual_matches": combined_results,
            "query_type": "image"  # Confirm type
        }
        
    except Exception as e:
        print(f">>> VISUAL AGENT ERROR: {type(e).__name__}: {str(e)}")
        logger.error(f"Visual Search Error: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content="Sorry, I had trouble analyzing that image. Please try again or describe what you're looking for.")],
            "error": str(e)
        }

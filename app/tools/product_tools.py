"""
Product search tools for the Awelewa agent system.
All tools follow the LangChain @tool pattern for LLM binding.
"""
from langchain.tools import tool
from app.tools.db_tools import get_product_details
from app.tools.pos_connector_tools import search_phppos_products
import logging

logger = logging.getLogger(__name__)


@tool("search_products_tool")
async def search_products(query: str) -> str:
    """
    Search for products using text query (searches Knowledge Server + POS).
    """
    try:
        print(f"\n>>> TOOL: search_products called with query='{query}'")
        logger.info(f"Product search tool called via MCP: '{query}'")
        
        # 1. Search via Knowledge MCP (Semantic)
        from app.services.mcp_service import mcp_service
        
        # Note: Knowledge Server returns formatted string of matches.
        knowledge_result = await mcp_service.call_tool("knowledge", "search_memory", {"query": query})
        
        # If knowledge search fails or returns "No matching products", we try POS fallback.
        # But wait, Knowledge Server uses Pinecone which has the same data as before.
        
        if knowledge_result and "No matching products" not in knowledge_result and "Error" not in knowledge_result:
             return f"[Semantic Search Results]\n{knowledge_result}"

        # 2. Fallback to direct POS search (Exact Match)
        logger.info("Knowledge search returned little/no results. Trying direct POS.")
        pos_results = await search_phppos_products.ainvoke(query)
        return f"[POS Search Results]\n{pos_results}"
        
    except Exception as e:
        logger.error(f"Product search failed: {e}", exc_info=True)
        return f"I encountered an error searching for products. Please try again."


@tool("get_product_by_id_tool")
async def get_product_by_id(product_id: str) -> str:
    """
    Get detailed information about a specific product by ID.
    
    Args:
        product_id: The product identifier
        
    Returns:
        Detailed product information including price, stock, description
    """
    try:
        logger.info(f"Getting product details for ID: {product_id}")
        
        result = await get_product_details.ainvoke(product_id)
        
        if not result:
            return f"Product with ID '{product_id}' not found."
        
        return f"Product Details:\n{result}"
        
    except Exception as e:
        logger.error(f"Product detail fetch failed: {e}")
        return f"Could not retrieve product details. Please try again."


@tool("check_product_stock_tool")
async def check_product_stock(product_name: str) -> str:
    """
    Check if a specific product is in stock.
    
    Args:
        product_name: Name of the product to check
        
    Returns:
        Stock availability status
    """
    try:
        logger.info(f"Checking stock for: {product_name}")
        
        # Search for the product first
        search_result = await search_phppos_products.ainvoke(product_name)
        
        if "No products found" in search_result:
            return f"'{product_name}' is not available in our inventory."
        
        # Extract stock info from search results
        # The search results should include stock status
        return search_result
        
    except Exception as e:
        logger.error(f"Stock check failed: {e}")
        return "Could not check stock availability. Please contact support."

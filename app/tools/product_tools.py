"""
Product Tools: Search and stock check tools using MCP architecture.
"""
from langchain.tools import tool
from app.services.mcp_service import mcp_service
import logging

logger = logging.getLogger(__name__)


@tool("search_products_tool")
async def search_products(query: str) -> str:
    """Search for products using text query (Knowledge Server + POS fallback)."""
    try:
        logger.info(f"Product search: '{query}'")
        
        # Semantic search via Knowledge MCP
        knowledge_result = await mcp_service.call_tool("knowledge", "search_memory", {"query": query})
        
        if knowledge_result and "No matching products" not in knowledge_result and "Error" not in knowledge_result:
            return f"[Semantic Search Results]\n{knowledge_result}"

        # Fallback to direct POS search
        logger.info("Knowledge search returned no results. Trying POS.")
        pos_results = await search_pos_direct.ainvoke(query)
        return f"[POS Search Results]\n{pos_results}"
        
    except Exception as e:
        logger.error(f"Product search failed: {e}", exc_info=True)
        return "I encountered an error searching for products. Please try again."


@tool("get_product_by_id_tool")
async def get_product_by_id(product_id: str) -> str:
    """Get detailed information about a specific product by ID."""
    try:
        logger.info(f"Getting product: {product_id}")
        result = await mcp_service.call_tool("pos", "get_product_details", {"item_id": product_id})
        
        if not result or "Error" in result:
            return f"Product '{product_id}' not found."
        return result
        
    except Exception as e:
        logger.error(f"Product detail fetch failed: {e}")
        return "Could not retrieve product details. Please try again."


@tool("check_product_stock_tool")
async def check_product_stock(product_name: str) -> str:
    """Check if a specific product is in stock."""
    try:
        logger.info(f"Checking stock: {product_name}")
        result = await mcp_service.call_tool("pos", "search_products", {"query": product_name})
        
        if not result or "No matching products" in result:
            return f"'{product_name}' is not available in our inventory."
        return result
        
    except Exception as e:
        logger.error(f"Stock check failed: {e}")
        return "Could not check stock. Please contact support."


@tool("search_pos_direct_tool")
async def search_pos_direct(query: str) -> str:
    """Search products via MCP POS Server directly (exact match)."""
    logger.info(f"Direct POS search: '{query}'")
    
    mcp_result = await mcp_service.call_tool("pos", "search_products", {"query": query})
    if mcp_result and "Error" not in mcp_result:
        return mcp_result
    
    logger.warning(f"MCP Search failed: {mcp_result}")
    return "I'm having trouble connecting to our inventory. Please try again or contact us at the store."

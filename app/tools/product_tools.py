"""
Product search tools for the Awelewa agent system.
All tools follow the LangChain @tool pattern for LLM binding.
"""
from langchain.tools import tool
from langchain.tools import tool
from app.tools.db_tools import get_product_details
from app.services.db_service import AsyncSessionLocal
from app.models.db_models import Product, Order
from sqlalchemy import text
from app.utils.config import settings
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
        pos_results = await search_pos_direct.ainvoke(query)
        return f"[POS Search Results]\n{pos_results}"
        
    except Exception as e:
        logger.error(f"Product search failed: {e}", exc_info=True)
        return f"I encountered an error searching for products. Please try again."


@tool("get_product_by_id_tool")
async def get_product_by_id(product_id: str) -> str:
    """
    Get detailed information about a specific product by ID via MCP.
    """
    try:
        logger.info(f"Getting product details for ID: {product_id}")
        
        # Use MCP Service directly
        from app.services.mcp_service import mcp_service
        result = await mcp_service.call_tool("pos", "get_product_details", {"item_id": product_id})
        
        if not result or "Error" in result:
             # Fallback to fuzzy search if ID fails? Unlikely if ID is correct.
             return f"Product with ID '{product_id}' not found or error occurred: {result}"
        
        return result
        
    except Exception as e:
        logger.error(f"Product detail fetch failed: {e}")
        return f"Could not retrieve product details. Please try again."


@tool("check_product_stock_tool")
async def check_product_stock(product_name: str) -> str:
    """
    Check if a specific product is in stock via MCP.
    """
    try:
        logger.info(f"Checking stock for: {product_name}")
        
        # We use search_products via MCP because 'check_stock' in server might expect ID.
        # If product_name is a name, search is safer.
        from app.services.mcp_service import mcp_service
        # If the input looks like an ID, we could use check_stock(id), but name is common.
        # Let's stick to search logic which returns stock.
        
        result = await mcp_service.call_tool("pos", "search_products", {"query": product_name})
        
        if not result or "No matching products" in result:
             return f"'{product_name}' is not available in our inventory."
             
        return result
        
    except Exception as e:
        logger.error(f"Stock check failed: {e}")
        return "Could not check stock availability. Please contact support."

@tool("search_pos_direct_tool")
async def search_pos_direct(query: str) -> str:
    """
    Search for products via the MCP POS Server directly (Exact SKU/Name match).
    """
    logger.info(f"Using MCP for Direct POS Search: '{query}'")
    
    # Imports inside tool to delay dependency
    from app.services.mcp_service import mcp_service 
    
    # 1. Try MCP Server
    mcp_result = await mcp_service.call_tool("pos", "search_products", {"query": query})
    if mcp_result and "Error" not in mcp_result:
        return mcp_result
        
    logger.warning(f"MCP Search failed/returned error: {mcp_result}. Falling back to Mock.")

    # 2. Mock Fallback (if MCP unavailable)
    return """
[MOCK - MCP DISCONNECTED]
- ID: 999
  Name: Nivea Body Lotion (Local Mock)
  Price: ₦4,500
  Stock: 15
  Desc: Deep moisture for dry skin.
"""

# Note: sync_inventory_from_pos and push_order_to_pos have been removed 
# as the system now relies on live MCP connection to POS.

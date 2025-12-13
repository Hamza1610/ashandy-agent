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
        search_result = await search_pos_direct.ainvoke(product_name)
        
        if "No products found" in search_result:
            return f"'{product_name}' is not available in our inventory."
        
        # Extract stock info from search results
        # The search results should include stock status
        return search_result
        
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
        
    logger.warning(f"MCP Search failed/returned error: {mcp_result}. Falling back.")

    # 2. Mock Fallback (if MCP unavailable)
    return \"\"\"
[MOCK - MCP DISCONNECTED]
- ID: 999
  Name: Nivea Body Lotion (Local Mock)
  Price: ₦4,500
  Stock: 15
  Desc: Deep moisture for dry skin.
\"\"\"

@tool
async def sync_inventory_from_pos(data: list) -> str:
    """
    Sync inventory data coming from the local POS.
    Data should be a list of product dictionaries: [{'sku': '...', 'qty': 10, 'price': 5000}, ...]
    """
    if not data:
        return "No data provided."

    count = 0
    try:
        async with AsyncSessionLocal() as session:
            for item in data:
                sku = item.get('sku')
                qty = item.get('qty', 0)
                price = item.get('price')
                
                # Update product logic
                # Finding by SKU
                result = await session.execute(text("SELECT product_id FROM products WHERE sku = :sku"), {"sku": sku})
                prod_row = result.fetchone()
                
                if prod_row:
                    # Update (simplified query, avoiding ORM overhead for bulk speed in tool)
                    await session.execute(
                        text("UPDATE products SET price = :price, metadata = jsonb_set(COALESCE(metadata, '{}'), '{inventory_count}', :qty) WHERE sku = :sku"),
                        {"price": price, "qty": str(qty), "sku": sku}
                    )
                    count += 1
                else:
                    logger.warning(f"Product SKU {sku} not found for sync.")
            
            await session.commit()
            return f"Synced {count} items from POS."
            
    except Exception as e:
        logger.error(f"POS Sync error: {e}")
        return f"Sync failed: {e}"

@tool
async def push_order_to_pos(order_id: str) -> str:
    """
    Queue an order to be picked up by the local POS connector.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Check if order exists
            result = await session.execute(text("SELECT status FROM orders WHERE order_id = :oid"), {"oid": order_id})
            order = result.fetchone()
            if not order:
                return f"Order {order_id} not found."
            
            # Update status to indicate ready for POS
            await session.execute(
                text("UPDATE orders SET status = 'queued_for_pos' WHERE order_id = :oid"),
                {"oid": order_id}
            )
            await session.commit()
            return f"Order {order_id} queued for POS sync."
    except Exception as e:
        logger.error(f"Push to POS error: {e}")
        return f"Failed to queue order: {e}"

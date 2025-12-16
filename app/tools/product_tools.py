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
            # Filter out stock count mentions from results
            lines = knowledge_result.split('\n')
            filtered = [l for l in lines if 'stock:' not in l.lower() and 'qty:' not in l.lower()]
            return f"[Semantic Search Results]\n{chr(10).join(filtered)}"

        # Fallback to direct POS search
        logger.info("Knowledge search returned no results. Trying POS.")
        pos_results = await search_pos_direct.ainvoke(query)
        
        # If still no results, try finding similar products
        if "No products found" in pos_results or not pos_results.strip():
            logger.info(f"No exact match for '{query}'. Searching for similar products...")
            
            # Extract keywords for similarity search
            keywords = query.lower().replace("price", "").replace("how much", "").split()
            for keyword in keywords[:2]:
                if len(keyword) > 3:  # Skip short words
                    similar = await mcp_service.call_tool("pos", "search_products", {"query": keyword})
                    if similar and "No products found" not in similar and "Error" not in similar:
                        # Filter stock counts
                        lines = similar.split('\n')
                        filtered = [l for l in lines if 'stock:' not in l.lower() and 'qty:' not in l.lower()]
                        return (
                            f"'{query}' is not in our current catalog.\n\n"
                            f"✨ *Similar products you might like:*\n{chr(10).join(filtered)}"
                        )
            
            return f"'{query}' is not available. Please ask about our other cosmetics products!"
        
        # Filter stock counts from POS results
        lines = pos_results.split('\n')
        filtered = [l for l in lines if 'stock:' not in l.lower() and 'qty:' not in l.lower()]
        return f"[POS Search Results]\n{chr(10).join(filtered)}"
        
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
    """
    Check if a product is available (name found in database = available).
    
    NOTE: Stock counts are NOT reliable (PHPPOS not up-to-date).
    If product name exists → Consider available.
    If not found → Recommend similar products.
    
    For orders >25k, manager confirms actual availability before payment.
    """
    try:
        logger.info(f"Checking availability: {product_name}")
        result = await mcp_service.call_tool("pos", "search_products", {"query": product_name})
        
        if not result or "No matching products" in result or "Error" in result:
            # Product not found - try to find similar products
            logger.info(f"'{product_name}' not found. Searching for similar products...")
            
            # Extract key terms for similarity search
            keywords = product_name.lower().split()
            similar_results = []
            
            for keyword in keywords[:2]:  # Try first 2 keywords
                if len(keyword) > 3:  # Skip short words
                    similar = await mcp_service.call_tool("pos", "search_products", {"query": keyword})
                    if similar and "No matching" not in similar:
                        similar_results.append(similar)
            
            if similar_results:
                return (
                    f"'{product_name}' is not currently in our catalog.\n\n"
                    f"✨ *Similar products you might like:*\n{similar_results[0]}"
                )
            else:
                return f"'{product_name}' is not available. Please ask about our other products!"
        
        # Product found - it's available (don't mention stock counts)
        # Parse out stock counts from response before returning
        lines = result.split('\n')
        filtered_lines = []
        for line in lines:
            # Remove stock/quantity mentions
            if 'stock:' not in line.lower() and 'qty:' not in line.lower() and 'quantity:' not in line.lower():
                filtered_lines.append(line)
        
        clean_result = '\n'.join(filtered_lines)
        return f"✅ {product_name} is available!\n{clean_result}"
        
    except Exception as e:
        logger.error(f"Availability check failed: {e}")
        return "Could not check availability. Please contact support."


@tool("search_pos_direct_tool")
async def search_pos_direct(query: str) -> str:
    """Search products via MCP POS Server directly (exact match)."""
    logger.info(f"Direct POS search: '{query}'")
    
    mcp_result = await mcp_service.call_tool("pos", "search_products", {"query": query})
    if mcp_result and "Error" not in mcp_result:
        return mcp_result
        
    logger.warning(f"MCP Search failed/returned error: {mcp_result}. Falling back.")

    # 2. Mock Fallback (if MCP unavailable)
    return """
[MOCK - MCP DISCONNECTED]
- ID: 999
  Name: Nivea Body Lotion (Local Mock)
  Price: ₦4,500
  Stock: 15
  Desc: Deep moisture for dry skin.
"""

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

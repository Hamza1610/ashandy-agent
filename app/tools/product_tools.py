"""
Product Tools: Search and stock check tools using MCP architecture.
"""
from langchain.tools import tool
from sqlalchemy import text
from app.services.mcp_service import mcp_service
from app.services.db_service import AsyncSessionLocal
import logging

logger = logging.getLogger(__name__)


async def alert_manager_non_skincare(user_id: str, category: str, product_name: str):
    """
    Alert manager when customer asks about non-skincare products.
    Called internally when detecting non-skincare inquiries.
    """
    try:
        from app.services.meta_service import meta_service
        from app.utils.config import settings
        
        message = (
            f"📢 Non-skincare inquiry\n"
            f"Customer: {user_id}\n"
            f"Category: {category}\n"
            f"Product: {product_name}\n"
            f"Action: Customer wants this item - please follow up!"
        )
        
        if not settings.ADMIN_PHONE_NUMBERS:
            logger.warning("⚠️ ADMIN_PHONE_NUMBERS not configured - cannot alert manager!")
            return
        
        for admin_phone in settings.ADMIN_PHONE_NUMBERS:
            result = await meta_service.send_whatsapp_text(admin_phone, message)
            if result and result.get("status") == "error":
                logger.error(f"❌ Failed to alert manager {admin_phone}: {result.get('error')}")
            else:
                logger.info(f"✅ Alerted manager {admin_phone} about inquiry for '{product_name}'")
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to alert manager: {e}")


@tool("search_products_tool")
async def search_products(query: str, user_id: str = "unknown") -> str:
    """
    Search for products using complete flow:
    1. Pinecone (all categories with updated prices)
    2. POS (skincare only - other categories have outdated prices)
    3. If not found → Alert manager + promise to follow up
    """
    try:
        logger.info(f"Product search: '{query}' for user {user_id}")
        
        # STEP 1: Semantic search via Knowledge MCP (Pinecone - all categories OK)
        # Use search_products for semantic product search (not search_memory which is for user history)
        knowledge_result = await mcp_service.call_tool("knowledge", "search_products", {"query": query})
        
        if knowledge_result and "No matching products" not in knowledge_result and "Error" not in knowledge_result:
            # Filter out stock count mentions from results
            lines = knowledge_result.split('\n')
            filtered = [l for l in lines if 'stock:' not in l.lower() and 'qty:' not in l.lower() and l.strip()]
            # Format as conversational response
            return f"Here's what I found for you:\n\n" + chr(10).join(filtered)

        # STEP 2: Fallback to POS (skincare only)
        logger.info("Pinecone search returned no results. Trying POS (skincare only).")
        pos_results = await search_pos_direct.ainvoke(query)
        
        if pos_results and "No matching skincare" not in pos_results and "Error" not in pos_results:
            # Filter stock counts from POS results
            lines = pos_results.split('\n')
            filtered = [l for l in lines if 'stock:' not in l.lower() and 'qty:' not in l.lower() and l.strip()]
            # Format as conversational response
            return f"Here's what I found for you:\n\n" + chr(10).join(filtered)
        
        # STEP 3: Try finding similar skincare products
        logger.info(f"No exact match for '{query}'. Searching for similar skincare...")
        keywords = query.lower().replace("price", "").replace("how much", "").split()
        for keyword in keywords[:2]:
            if len(keyword) > 3:
                similar = await mcp_service.call_tool("pos", "search_products", {"query": keyword})
                if similar and "No matching skincare" not in similar and "Error" not in similar:
                    lines = similar.split('\n')
                    filtered = [l for l in lines if 'stock:' not in l.lower() and 'qty:' not in l.lower() and l.strip()]
                    return (
                        f"I don't have an exact match for '{query}', but here are some similar products you might like:\n\n"
                        + chr(10).join(filtered)
                    )
        
        # STEP 4: Product not found anywhere - Alert manager and promise follow-up
        logger.info(f"Product '{query}' not found. Alerting manager.")
        await alert_manager_non_skincare(
            user_id=user_id,
            category="unknown",
            product_name=query
        )
        
        # Return customer-friendly message (NOT raw instructions)
        return (
            f"I couldn't find '{query}' in our current inventory. "
            f"I've notified our manager and they'll check availability for you! "
            f"They'll reach out shortly. 💕 In the meantime, is there anything else I can help you with?"
        )
        
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
    
    # DEBUG: Log exactly what MCP returned
    logger.info(f"🔍 MCP POS raw result: {repr(mcp_result[:200] if mcp_result else 'None')}")
    
    if mcp_result and "Error" not in mcp_result and "No matching" not in mcp_result and "No products" not in mcp_result:
        return mcp_result
    
    # Fallback to local mock data if MCP fails or returns nothing
    logger.info(f"MCP returned no results or error. Using local mock data fallback.")
    
    try:
        import json
        from pathlib import Path
        mock_path = Path(__file__).parent.parent.parent / "mocks" / "products.json"
        with open(mock_path, "r") as f:
            data = json.load(f)
        
        # Improved search: match any query word against name OR description
        # Add synonyms for UK/US spellings and common cosmetic terms
        SYNONYMS = {
            "moisturiser": ["moisturizer", "moisturizing", "cream", "lotion"],
            "moisturizer": ["moisturiser", "moisturizing", "cream", "lotion"],
            "cleanser": ["face wash", "facial", "cleansing"],
            "face wash": ["cleanser", "facial", "cleansing"],
            "toner": ["toning", "tonic"],
            "serum": ["essence", "treatment"],
        }
        
        query_words = query.lower().split()
        # Expand query with synonyms
        expanded_words = set(query_words)
        for word in query_words:
            if word in SYNONYMS:
                expanded_words.update(SYNONYMS[word])
        
        def matches_product(p):
            if p.get("category_id", p.get("category", "")).upper() != "SKIN CARE":
                return False
            name = p.get("name", "").lower()
            desc = p.get("description", "").lower()
            text = f"{name} {desc}"
            # Match if any expanded query word is in name or description
            return any(word in text for word in expanded_words if len(word) > 2)
        
        matches = [p for p in data.get("products", []) if matches_product(p)][:5]
        
        if matches:
            result = ""
            for p in matches:
                result += f"""
- ID: {p.get('item_id')}
  Name: {p.get('name')}
  Price: ₦{p.get('unit_price'):,}
  Desc: {p.get('description', 'N/A')}
"""
            return result
    except Exception as e:
        logger.error(f"Mock data fallback failed: {e}")
    
    return f"No matching skincare products found for '{query}'."

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

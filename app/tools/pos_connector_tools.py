from langchain.tools import tool
from app.services.db_service import AsyncSessionLocal
from app.models.db_models import Product, Order
from sqlalchemy import text
from app.utils.config import settings
import httpx
import logging

logger = logging.getLogger(__name__)

@tool
async def search_phppos_products(query: str) -> str:
    """
    Search for products, prices, and inventory directly from the PHPPOS system.
    Use this to get the most up-to-date details when a user asks about a specific product.
    """
    url = f"{settings.PHPPOS_BASE_URL}/items" 
    headers = {
        "accept": "application/json",
        "x-api-key": settings.POS_CONNECTOR_API_KEY,
        "User-Agent": "curl/8.5.0"
    }
    
    logger.info(f"Executing search_phppos_products with query: '{query}'")
    
    try:
        # Note: The API might support ?search_term= or similar. 
        # If specific search param isn't documented, we might fetch recent/all and filter (inefficient but works for MVP/small catalog)
        # OR we assume the query is an ID.
        # Let's try appending search param if supported, otherwise filtering in memory.
        # Based on typical PHPPOS, usually there's a search parameter. Let's try 'search'.
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # We'll try fetching all and filtering in python for now to be safe, 
            # unless catalogue is huge. User indicated "fetch the product".
            # Optimization: Use ingestion cache (Pinecone) for "Search" and this tool for "Details" if specific.
            # But user wants this tool to "fetch product".
            
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            items = response.json()
            
            # Simple fuzzy filter in Python
            matches = []
            query_lower = query.lower()
            
            for item in items:
                name = item.get("name", "").lower()
                # Check Name or Item ID
                if query_lower in name or query_lower == str(item.get("item_id")):
                    matches.append(item)
                    if len(matches) >= 5: # Limit results
                        break
            
            if not matches:
                return "No matching products found in POS."
                
            # Format output
            result_str = ""
            for m in matches:
                # Extract clean details
                qty_data = m.get("locations", {}).get("1", {}).get("quantity", "N/A") # Assuming Loc 1
                price = int(float(m.get("unit_price", 0)))
                result_str += f"""
- ID: {m.get('item_id')}
  Name: {m.get('name')}
  Price: ₦{price:,}
  Stock: {qty_data}
  Desc: {m.get('description', 'N/A')}
"""
            return result_str

    except Exception as e:
        logger.error(f"PHPPOS Fetch Error: {e}")
        return "Error connecting to POS system."

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
                    # Create new or log missing (skipping create for now to keep tool simple focused on sync)
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


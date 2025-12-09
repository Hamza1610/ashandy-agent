from langchain.tools import tool
from app.services.db_service import AsyncSessionLocal
from app.models.db_models import Product, Order
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

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


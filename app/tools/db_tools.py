from langchain.tools import tool
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.models.db_models import User, Product, Order
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

@tool
async def check_admin_whitelist(phone_number: str) -> bool:
    """Check if a phone number is in the admin whitelist (via environment variable)."""
    from app.utils.config import settings
    if phone_number in settings.ADMIN_PHONE_NUMBERS:
        return True
    return False

@tool
async def get_product_details(product_name_or_sku: str) -> str:
    """Retrieve product details from the database by name or SKU."""
    async with AsyncSessionLocal() as session:
        # Simple fuzzy search implementation using ILIKE
        query = text("""
            SELECT name, price, description, sku
            FROM products 
            WHERE name ILIKE :term OR sku ILIKE :term
            LIMIT 5
        """)
        result = await session.execute(query, {"term": f"%{product_name_or_sku}%"})
        products = result.fetchall()
        
        if not products:
            return "No products found."
        
        response = "Found products:\n"
        for p in products:
            response += f"- {p.name} ({p.sku}): ₦{p.price}\n  {p.description}\n"
        return response

@tool
async def create_order_record(user_id: str, amount: float, reference: str) -> str:
    """Create a new order record in the database."""
    # Logic to insert order
    pass

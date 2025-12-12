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

async def create_order_record(user_id: str, amount: float, reference: str, details: Dict = None) -> str:
    """Create a new order record in the database."""
    async with AsyncSessionLocal() as session:
        new_order = Order(
            user_id=user_id,
            total_amount=amount,
            status="pending",
            reference=reference,
            details=details or {}
        )
        session.add(new_order)
        await session.commit()
        return f"Order created with Ref: {reference}"

@tool
async def get_order_by_reference(reference: str) -> Dict:
    """Retrieve an order by its payment reference."""
    async with AsyncSessionLocal() as session:
        query = text("SELECT * FROM orders WHERE reference = :ref")
        result = await session.execute(query, {"ref": reference})
        order = result.fetchone()
        
        if not order:
            return {}
            
        # Assuming SQL returns row, convert to dict. 
        # details column is JSONB in standard setups, asyncpg handles it.
        return {
            "reference": order.reference,
            "amount": order.total_amount,
            "user_id": order.user_id,
            "details": order.details,
            "status": order.status
        }

@tool
async def get_active_order_reference(user_id: str) -> str:
    """
    Retrieve the reference of the most recent PENDING order for a user.
    Useful for checking payment status when the user claims they paid.
    """
    async with AsyncSessionLocal() as session:
        # Get the latest 'pending' order
        query = text("""
            SELECT reference FROM orders 
            WHERE user_id = :uid AND status = 'pending' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = await session.execute(query, {"uid": user_id})
        record = result.fetchone()
        
        if record:
            return record.reference
        return "No pending order found."

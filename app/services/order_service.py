"""
Order Service: CRUD operations for order management
Handles order creation, retrieval, and status updates for payment and delivery tracking
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_models import Order, User
from app.services.db_service import AsyncSessionLocal
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def create_order(
    user_id: str,
    paystack_reference: str,
    customer_email: str,
    customer_name: str,
    customer_phone: str,
    items: List[Dict],
    items_total: float,
    transport_fee: float,
    total_amount: float,
    payment_link: str,
    delivery_address: str = "To be confirmed",
    pickup_location: str = "Ashandy Store, Ibadan"
) -> Order:
    """
    Create a new order after payment link generation.
    
    Args:
        user_id: WhatsApp/Instagram user ID
        paystack_reference: Unique Paystack reference
        customer_email: Customer's email
        customer_name: Customer's name
        customer_phone: Customer's phone
        items: List of order items [{"name": "...", "price": ..., "quantity": ...}]
        items_total: Subtotal of items
        transport_fee: Delivery fee
        total_amount: Total (items + transport)
        payment_link: Generated Paystack URL
        delivery_address: Delivery location
        pickup_location: Store location
        
    Returns:
        Created Order object
    """
    async with AsyncSessionLocal() as session:
        try:
            # Find or create user
            # For now, we'll use user_id directly since we don't have user creation yet
            # TODO: Implement proper user lookup/creation
            
            order = Order(
                # user_id=user_uuid,  # Skip for now, nullable in schema
                paystack_reference=paystack_reference,
                customer_email=customer_email,
                customer_name=customer_name,
                customer_phone=customer_phone,
                items=items,
                items_total=items_total,
                transport_fee=transport_fee,
                total_amount=total_amount,
                payment_link=payment_link,
                delivery_address=delivery_address,
                pickup_location=pickup_location,
                payment_status="pending",
                delivery_status="pending",
                status="pending"
            )
            
            session.add(order)
            await session.commit()
            await session.refresh(order)
            
            logger.info(f"Order created: {order.order_id} (ref: {paystack_reference})")
            return order
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to create order: {e}", exc_info=True)
            raise


async def get_order_by_reference(reference: str) -> Optional[Order]:
    """
    Retrieve order by Paystack reference.
    
    Args:
        reference: Paystack payment reference
        
    Returns:
        Order object or None if not found
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Order).where(Order.paystack_reference == reference)
            )
            order = result.scalar_one_or_none()
            
            if order:
                logger.info(f"Order found: {order.order_id} for reference {reference}")
            else:
                logger.warning(f"No order found for reference: {reference}")
                
            return order
            
        except Exception as e:
            logger.error(f"Failed to get order by reference: {e}", exc_info=True)
            return None


async def get_order_by_id(order_id: UUID) -> Optional[Order]:
    """
    Retrieve order by ID.
    
    Args:
        order_id: Order UUID
        
    Returns:
        Order object or None if not found
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Order).where(Order.order_id == order_id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get order by ID: {e}", exc_info=True)
            return None


async def update_order_status(
    reference: str,
    payment_status: Optional[str] = None,
    delivery_status: Optional[str] = None,
    paid_at: Optional[datetime] = None
) -> Optional[Order]:
    """
    Update order payment and/or delivery status.
    
    Args:
        reference: Paystack reference
        payment_status: New payment status (pending, paid, failed)
        delivery_status: New delivery status (pending, assigned, out_for_delivery, delivered)
        paid_at: Payment timestamp
        
    Returns:
        Updated Order object or None if not found
    """
    async with AsyncSessionLocal() as session:
        try:
            # Get order
            result = await session.execute(
                select(Order).where(Order.paystack_reference == reference)
            )
            order = result.scalar_one_or_none()
            
            if not order:
                logger.warning(f"Cannot update: Order not found for reference {reference}")
                return None
            
            # Update fields
            if payment_status:
                order.payment_status = payment_status
                logger.info(f"Order {order.order_id}: payment_status → {payment_status}")
                
            if delivery_status:
                order.delivery_status = delivery_status
                logger.info(f"Order {order.order_id}: delivery_status → {delivery_status}")
                
            if paid_at:
                order.paid_at = paid_at
                
            # Update legacy status field
            if payment_status == "paid":
                order.status = "paid"
            elif delivery_status == "delivered":
                order.status = "delivered"
            
            await session.commit()
            await session.refresh(order)
            
            logger.info(f"Order {order.order_id} updated successfully")
            return order
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to update order status: {e}", exc_info=True)
            return None


async def get_user_orders(user_phone: str) -> List[Order]:
    """
    Get all orders for a user by phone number.
    
    Args:
        user_phone: Customer phone number
        
    Returns:
        List of Order objects
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Order)
                .where(Order.customer_phone == user_phone)
                .order_by(Order.created_at.desc())
            )
            orders = result.scalars().all()
            
            logger.info(f"Found {len(orders)} orders for user {user_phone}")
            return list(orders)
            
        except Exception as e:
            logger.error(f"Failed to get user orders: {e}", exc_info=True)
            return []


async def get_orders_by_status(
    payment_status: Optional[str] = None,
    delivery_status: Optional[str] = None,
    limit: int = 100
) -> List[Order]:
    """
    Get orders filtered by status (for admin).
    
    Args:
        payment_status: Filter by payment status
        delivery_status: Filter by delivery status
        limit: Maximum number of orders to return
        
    Returns:
        List of Order objects
    """
    async with AsyncSessionLocal() as session:
        try:
            query = select(Order)
            
            if payment_status:
                query = query.where(Order.payment_status == payment_status)
                
            if delivery_status:
                query = query.where(Order.delivery_status == delivery_status)
            
            query = query.order_by(Order.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            orders = result.scalars().all()
            
            logger.info(f"Found {len(orders)} orders (payment={payment_status}, delivery={delivery_status})")
            return list(orders)
            
        except Exception as e:
            logger.error(f"Failed to get orders by status: {e}", exc_info=True)
            return []

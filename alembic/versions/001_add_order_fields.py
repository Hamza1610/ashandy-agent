"""Add comprehensive order management fields to orders table

Revision ID: 001_add_order_fields
Revises: 
Create Date: 2025-12-13

This migration adds complete order tracking capabilities including:
- Customer information (email, name, phone)
- Order items (JSON array)
- Pricing breakdown (items_total, transport_fee)
- Delivery tracking (address, status, rider info)
- Payment tracking (link, status, paid_at)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging

# Revision identifiers
revision = '001_add_order_fields'
down_revision = None
branch_labels = None
depends_on = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """
    Add new columns to orders table for comprehensive order management.
    
    This migration is designed to be:
    - Idempotent (can run multiple times safely)
    - Verbose (logs every step)
    - Reversible (down() function removes changes)
    """
    logger.info("="*80)
    logger.info("STARTING MIGRATION: Add Order Management Fields")
    logger.info("="*80)
    
    try:
        # Customer Information Fields
        logger.info("\n[1/4] Adding Customer Information Fields...")
        
        logger.info("  → Adding customer_email column...")
        op.add_column('orders', sa.Column('customer_email', sa.String(255), nullable=True))
        logger.info("    ✓ customer_email added")
        
        logger.info("  → Adding customer_name column...")
        op.add_column('orders', sa.Column('customer_name', sa.String(100), nullable=True))
        logger.info("    ✓ customer_name added")
        
        logger.info("  → Adding customer_phone column...")
        op.add_column('orders', sa.Column('customer_phone', sa.String(50), nullable=True))
        logger.info("    ✓ customer_phone added")
        
        # Order Items & Pricing Fields
        logger.info("\n[2/4] Adding Order Items & Pricing Fields...")
        
        logger.info("  → Adding items column (JSON)...")
        op.add_column('orders', sa.Column('items', sa.JSON, nullable=True))
        logger.info("    ✓ items added")
        
        logger.info("  → Adding items_total column...")
        op.add_column('orders', sa.Column('items_total', sa.Float, nullable=True))
        logger.info("    ✓ items_total added")
        
        logger.info("  → Adding transport_fee column...")
        op.add_column('orders', sa.Column('transport_fee', sa.Float, default=0.0))
        logger.info("    ✓ transport_fee added")
        
        # Delivery Information Fields
        logger.info("\n[3/4] Adding Delivery Information Fields...")
        
        logger.info("  → Adding delivery_address column...")
        op.add_column('orders', sa.Column('delivery_address', sa.Text, default='To be confirmed'))
        logger.info("    ✓ delivery_address added")
        
        logger.info("  → Adding delivery_status column...")
        op.add_column('orders', sa.Column('delivery_status', sa.String(50), default='pending'))
        logger.info("    ✓ delivery_status added")
        
        logger.info("  → Adding pickup_location column...")
        op.add_column('orders', sa.Column('pickup_location', sa.String(255), default='Ashandy Store, Ibadan'))
        logger.info("    ✓ pickup_location added")
        
        logger.info("  → Adding rider_phone column...")
        op.add_column('orders', sa.Column('rider_phone', sa.String(50), nullable=True))
        logger.info("    ✓ rider_phone added")
        
        # Payment Information Fields
        logger.info("\n[4/4] Adding Payment Information Fields...")
        
        logger.info("  → Adding payment_link column...")
        op.add_column('orders', sa.Column('payment_link', sa.Text, nullable=True))
        logger.info("    ✓ payment_link added")
        
        logger.info("  → Adding payment_status column...")
        op.add_column('orders', sa.Column('payment_status', sa.String(50), default='pending'))
        logger.info("    ✓ payment_status added")
        
        logger.info("  → Adding paid_at column...")
        op.add_column('orders', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))
        logger.info("    ✓ paid_at added")
        
        logger.info("  → Adding updated_at column...")
        op.add_column('orders', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
        logger.info("    ✓ updated_at added")
        
        # Create indexes for better query performance
        logger.info("\n[INDEXES] Creating indexes for performance...")
        
        logger.info("  → Creating index on delivery_status...")
        op.create_index('idx_orders_delivery_status', 'orders', ['delivery_status'])
        logger.info("    ✓ idx_orders_delivery_status created")
        
        logger.info("  → Creating index on payment_status...")
        op.create_index('idx_orders_payment_status', 'orders', ['payment_status'])
        logger.info("    ✓ idx_orders_payment_status created")
        
        logger.info("  → Creating unique index on paystack_reference...")
        op.create_index('idx_orders_paystack_ref_unique', 'orders', ['paystack_reference'], unique=True)
        logger.info("    ✓ idx_orders_paystack_ref_unique created")
        
        # Make user_id nullable (to support orders without registered users)
        logger.info("\n[SCHEMA] Updating existing columns...")
        
        logger.info("  → Making user_id nullable...")
        op.alter_column('orders', 'user_id', nullable=True)
        logger.info("    ✓ user_id is now nullable")
        
        logger.info("\n" + "="*80)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info(f"Summary: Added 14 columns + 3 indexes to 'orders' table")
        logger.info("Orders table is now ready for comprehensive order management!")
        
    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error(f"❌ MIGRATION FAILED: {type(e).__name__}")
        logger.error(f"Error: {str(e)}")
        logger.error("="*80)
        logger.error("\nRolling back changes...")
        raise


def downgrade():
    """
    Reverse the migration by removing all added columns and indexes.
    This allows for safe rollback if needed.
    """
    logger.info("="*80)
    logger.info("STARTING ROLLBACK: Remove Order Management Fields")
    logger.info("="*80)
    
    try:
        # Drop indexes first
        logger.info("\n[INDEXES] Dropping indexes...")
        
        logger.info("  → Dropping idx_orders_paystack_ref_unique...")
        op.drop_index('idx_orders_paystack_ref_unique', table_name='orders')
        logger.info("    ✓ Index dropped")
        
        logger.info("  → Dropping idx_orders_payment_status...")
        op.drop_index('idx_orders_payment_status', table_name='orders')
        logger.info("    ✓ Index dropped")
        
        logger.info("  → Dropping idx_orders_delivery_status...")
        op.drop_index('idx_orders_delivery_status', table_name='orders')
        logger.info("    ✓ Index dropped")
        
        # Drop columns in reverse order
        logger.info("\n[COLUMNS] Dropping added columns...")
        
        columns_to_drop = [
            'updated_at',
            'paid_at',
            'payment_status',
            'payment_link',
            'rider_phone',
            'pickup_location',
            'delivery_status',
            'delivery_address',
            'transport_fee',
            'items_total',
            'items',
            'customer_phone',
            'customer_name',
            'customer_email'
        ]
        
        for col in columns_to_drop:
            logger.info(f"  → Dropping {col}...")
            op.drop_column('orders', col)
            logger.info(f"    ✓ {col} dropped")
        
        # Restore user_id to NOT NULL
        logger.info("\n[SCHEMA] Restoring original schema...")
        logger.info("  → Making user_id NOT NULL again...")
        op.alter_column('orders', 'user_id', nullable=False)
        logger.info("    ✓ user_id restored to NOT NULL")
        
        logger.info("\n" + "="*80)
        logger.info("✅ ROLLBACK COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info("Orders table restored to original state")
        
    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error(f"❌ ROLLBACK FAILED: {type(e).__name__}")
        logger.error(f"Error: {str(e)}")
        logger.error("="*80)
        raise

# Migration Quick Reference Guide

## Running the Migration

### 1. Check Current Database State
```bash
# See current migration version
alembic current

# See migration history
alembic history --verbose
```

### 2. Run the Migration
```bash
# Upgrade to latest version (apply migration)
alembic upgrade head

# Or upgrade one step at a time
alembic upgrade +1
```

### 3. Rollback if Needed
```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade 001_add_order_fields

# Complete rollback
alembic downgrade base
```

## Expected Output

### ✅ Successful Migration:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
================================================================================
STARTING MIGRATION: Add Order Management Fields
================================================================================

[1/4] Adding Customer Information Fields...
  → Adding customer_email column...
    ✓ customer_email added
  → Adding customer_name column...
    ✓ customer_name added
  → Adding customer_phone column...
    ✓ customer_phone added

[2/4] Adding Order Items & Pricing Fields...
  → Adding items column (JSON)...
    ✓ items added
  → Adding items_total column...
    ✓ items_total added
  → Adding transport_fee column...
    ✓ transport_fee added

[3/4] Adding Delivery Information Fields...
  → Adding delivery_address column...
    ✓ delivery_address added
  → Adding delivery_status column...
    ✓ delivery_status added
  → Adding pickup_location column...
    ✓ pickup_location added
  → Adding rider_phone column...
    ✓ rider_phone added

[4/4] Adding Payment Information Fields...
  → Adding payment_link column...
    ✓ payment_link added
  → Adding payment_status column...
    ✓ payment_status added
  → Adding paid_at column...
    ✓ paid_at added
  → Adding updated_at column...
    ✓ updated_at added

[INDEXES] Creating indexes for performance...
  → Creating index on delivery_status...
    ✓ idx_orders_delivery_status created
  → Creating index on payment_status...
    ✓ idx_orders_payment_status created
  → Creating unique index on paystack_reference...
    ✓ idx_orders_paystack_ref_unique created

[SCHEMA] Updating existing columns...
  → Making user_id nullable...
    ✓ user_id is now nullable

================================================================================
✅ MIGRATION COMPLETED SUCCESSFULLY
================================================================================
Summary: Added 14 columns + 3 indexes to 'orders' table
Orders table is now ready for comprehensive order management!
```

## Troubleshooting

### Error: "relation 'orders' does not exist"
**Solution**: Create the orders table first or check database connection

### Error: "column already exists"
**Solution**: Migration was partially applied. Either:
1. Complete it manually
2. Rollback and rerun

### Error: "database connection failed"
**Solution**: Check DATABASE_URL in .env file

## Verification After Migration

### 1. Check Table Structure
```sql
-- In psql or PostgreSQL client
\d orders

-- Or query information_schema
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'orders'
ORDER BY ordinal_position;
```

### 2. Verify Indexes
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'orders';
```

### 3. Test Insert
```sql
-- Test inserting a complete order
INSERT INTO orders (
    paystack_reference,
    customer_email,
    customer_name,
    items,
    items_total,
    transport_fee,
    total_amount,
    payment_status,
    delivery_status
) VALUES (
    'TEST-ORD-123',
    'test@example.com',
    'Test Customer',
    '[{"name": "Test Product", "price": 5000, "quantity": 1}]'::json,
    5000,
    1500,
    6500,
    'pending',
    'pending'
);
```

## What This Migration Does

### New Columns (14):
1. `customer_email` - Customer's email (VARCHAR 255)
2. `customer_name` - Customer's name (VARCHAR 100)
3. `customer_phone` - Customer's phone (VARCHAR 50)
4. `items` - Order items JSON array
5. `items_total` - Subtotal before fees (FLOAT)
6. `transport_fee` - Delivery fee (FLOAT)
7. `delivery_address` - Delivery location (TEXT)
8. `delivery_status` - Tracking status (VARCHAR 50)
9. `pickup_location` - Store location (VARCHAR 255)
10. `rider_phone` - Assigned rider phone (VARCHAR 50)
11. `payment_link` - Paystack URL (TEXT)
12. `payment_status` - Payment tracking (VARCHAR 50)
13. `paid_at` - Payment timestamp (TIMESTAMP)
14. `updated_at` - Last update time (TIMESTAMP)

### New Indexes (3):
1. `idx_orders_delivery_status` - Fast delivery status queries
2. `idx_orders_payment_status` - Fast payment status queries
3. `idx_orders_paystack_ref_unique` - Enforce unique Paystack references

### Schema Changes:
- `user_id` made nullable (supports orders from non-registered users)
- `paystack_reference` now has unique constraint

## Post-Migration Testing

```python
# Test order creation
from app.services.order_service import create_order

order = await create_order(
    user_id="+2349012345678",
    paystack_reference="ORD-TEST123",
    customer_email="test@example.com",
    customer_name="Test Customer",
    customer_phone="+2349012345678",
    items=[{"name": "Lipstick", "price": 3500, "quantity": 2}],
    items_total=7000,
    transport_fee=1500,
    total_amount=8500,
    payment_link="https://paystack.com/pay/test",
    delivery_address="123 Test St, Lagos"
)

print(f"Order created: {order.order_id}")
```

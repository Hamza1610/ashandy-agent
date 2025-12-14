"""
Database Auto-Migration: Creates tables automatically on app startup.
This eliminates the need to manually run psql commands.
"""
from sqlalchemy import text
from app.services.db_service import engine
import logging

logger = logging.getLogger(__name__)

# SQL statements to create all required tables
CREATE_TABLES_SQL = """
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id VARCHAR(255) UNIQUE NOT NULL,
    platform_source VARCHAR(50) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'customer',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phppos_item_id INTEGER UNIQUE,
    barcode VARCHAR(100),
    sku VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price FLOAT NOT NULL,
    category VARCHAR(100),
    image_url TEXT,
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    paystack_reference VARCHAR(100),
    total_amount FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    status VARCHAR(50) DEFAULT 'active',
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ
);

-- ============================================================
-- SYSTEM 3.0 TABLES (Analytics & Reporting)
-- ============================================================

CREATE TABLE IF NOT EXISTS message_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sentiment_score FLOAT DEFAULT 0.0,
    intent VARCHAR(50),
    platform VARCHAR(20) DEFAULT 'whatsapp',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_logs_user ON message_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_created ON message_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_message_logs_user_date ON message_logs(user_id, created_at);

CREATE TABLE IF NOT EXISTS customer_profiles (
    user_id VARCHAR(50) PRIMARY KEY,
    total_purchases FLOAT DEFAULT 0.0,
    order_count INT DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0.0,
    message_count INT DEFAULT 0,
    last_interaction TIMESTAMPTZ,
    preferred_categories JSONB DEFAULT '{}',
    retention_score FLOAT DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_summaries (
    date DATE PRIMARY KEY,
    total_orders INT DEFAULT 0,
    total_revenue FLOAT DEFAULT 0.0,
    unique_users INT DEFAULT 0,
    total_messages INT DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0.0,
    top_products JSONB DEFAULT '[]',
    stockout_requests JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    status VARCHAR(50) DEFAULT 'OPEN',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidents_user ON incidents(user_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
"""


async def run_auto_migration():
    """
    Run database migrations automatically.
    Creates all tables if they don't exist.
    Safe to run multiple times (idempotent).
    """
    try:
        async with engine.begin() as conn:
            # Split SQL into individual statements and execute each
            statements = [s.strip() for s in CREATE_TABLES_SQL.split(';') if s.strip()]
            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    try:
                        await conn.execute(text(stmt))
                    except Exception as e:
                        # Log but don't fail - some statements may already exist
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Migration statement warning: {e}")
            
            logger.info("✅ Database auto-migration completed successfully.")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database auto-migration failed: {e}")
        return False

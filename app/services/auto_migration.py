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

-- ============================================================
-- FEEDBACK LEARNING TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS feedback_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(100),
    message_id UUID,
    feedback_type VARCHAR(20) NOT NULL,
    feedback_signal VARCHAR(100),
    signal_strength VARCHAR(20),
    context_topic VARCHAR(100),
    previous_ai_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_logs(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_logs(created_at);

CREATE TABLE IF NOT EXISTS learned_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preference_type VARCHAR(50) NOT NULL,
    preference_key VARCHAR(100) NOT NULL,
    preference_data JSONB NOT NULL,
    confidence FLOAT DEFAULT 0.5,
    sample_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(preference_type, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_learned_prefs_type ON learned_preferences(preference_type);
"""


async def run_auto_migration():
    """
    Run database migrations automatically.
    Creates all tables if they don't exist.
    Executes each statement in a separate transaction to prevent cascade failures.
    """
    try:
        # Split SQL into individual statements
        statements = [s.strip() for s in CREATE_TABLES_SQL.split(';') if s.strip()]
        
        logger.info(f"Starting auto-migration ({len(statements)} statements)...")
        
        for i, stmt in enumerate(statements):
            # Clean statement of comments line by line
            lines = [line for line in stmt.splitlines() if not line.strip().startswith('--')]
            clean_stmt = '\n'.join(lines).strip()
            
            if not clean_stmt:
                continue

            try:
                # Use a separate transaction for each statement
                async with engine.begin() as conn:
                    await conn.execute(text(clean_stmt))
            except Exception as e:
                # Log specific errors but verify if it's critical
                err_msg = str(e).lower()
                if "already exists" in err_msg:
                    logger.debug(f"Skipping existing entity: {err_msg.split('\\n')[0]}")
                elif "relation" in err_msg and "does not exist" in err_msg:
                    # Critical dependency missing?
                    logger.error(f"❌ Dependency Error in migration step {i+1}: {e}")
                    # We continue, hoping future retries or manual fixes solve it, 
                    # but usually this implies out-of-order execution.
                else:
                    logger.warning(f"⚠️ Migration warning in step {i+1}: {e}")

        logger.info("✅ Database auto-migration completed.")
        return True
            
    except Exception as e:
        logger.error(f"❌ Database auto-migration fatal error: {e}")
        return False

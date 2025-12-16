-- ============================================================
-- ASHANDY COSMETICS - COMPLETE DATABASE SCHEMA
-- ============================================================
-- This file contains ALL database tables for the agent system.
-- Run with: psql -h localhost -U username -d database -f db_schema.sql
-- 
-- The app will also auto-create these tables on startup if they
-- don't exist, so manual migration is optional.
-- ============================================================

-- Enable UUID extension (required for gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- CORE TABLES (Original System)
-- ============================================================

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id VARCHAR(255) UNIQUE NOT NULL, -- Phone number or IG ID
    platform_source VARCHAR(50) NOT NULL, -- 'whatsapp' | 'instagram'
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'customer', -- 'admin' | 'customer'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

-- Products Table
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

-- Orders Table
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    paystack_reference VARCHAR(100),
    total_amount FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'paid' | 'synced'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat Sessions
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

-- Message Logs Table (Conversation Persistence)
CREATE TABLE IF NOT EXISTS message_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sentiment_score FLOAT DEFAULT 0.0,
    intent VARCHAR(50), -- 'purchase', 'inquiry', 'complaint', 'greeting', 'other'
    platform VARCHAR(20) DEFAULT 'whatsapp',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_logs_user ON message_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_created ON message_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_message_logs_user_date ON message_logs(user_id, created_at);

-- Customer Profiles Table (Retention & Pattern Tracking)
CREATE TABLE IF NOT EXISTS customer_profiles (
    user_id VARCHAR(50) PRIMARY KEY,
    total_purchases FLOAT DEFAULT 0.0,
    order_count INT DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0.0,
    message_count INT DEFAULT 0,
    last_interaction TIMESTAMPTZ,
    preferred_categories JSONB DEFAULT '{}',
    retention_score FLOAT DEFAULT 0.5,
    lead_score INT DEFAULT 0,              -- RFM-based lead scoring (0-100)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily Summaries Table (Pre-computed Aggregations)
CREATE TABLE IF NOT EXISTS daily_summaries (
    date DATE PRIMARY KEY,
    total_orders INT DEFAULT 0,
    total_revenue FLOAT DEFAULT 0.0,
    unique_users INT DEFAULT 0,
    total_messages INT DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0.0,
    top_products JSONB DEFAULT '[]', -- [{"id": 1, "name": "X", "count": 5}, ...]
    stockout_requests JSONB DEFAULT '[]', -- Products requested but out of stock
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Incidents Table (for escalations and handovers)
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    status VARCHAR(50) DEFAULT 'OPEN', -- 'OPEN', 'ESCALATED', 'RESOLVED'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidents_user ON incidents(user_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);

-- ============================================================
-- FEEDBACK LEARNING TABLES
-- ============================================================

-- Feedback Logs Table (User Reactions for Learning)
CREATE TABLE IF NOT EXISTS feedback_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(100),
    message_id UUID REFERENCES message_logs(id),
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('positive', 'negative', 'neutral')),
    feedback_signal VARCHAR(100),        -- The keyword/phrase that triggered detection
    signal_strength VARCHAR(20),          -- 'high', 'medium', 'low'
    context_topic VARCHAR(100),           -- What was discussed (product, delivery, etc)
    previous_ai_response TEXT,            -- What the AI said that got this reaction
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_logs(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_logs(created_at);

-- Learned Preferences Table (Aggregated Learning)
CREATE TABLE IF NOT EXISTS learned_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preference_type VARCHAR(50) NOT NULL, -- 'user', 'topic', 'global'
    preference_key VARCHAR(100) NOT NULL, -- user_id, topic name, or 'default'
    preference_data JSONB NOT NULL,       -- {style, tone, patterns, etc}
    confidence FLOAT DEFAULT 0.5,
    sample_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(preference_type, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_learned_prefs_type ON learned_preferences(preference_type);


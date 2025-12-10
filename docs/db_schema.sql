-- Database Schema Documentation

-- Users Table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform_id VARCHAR(255) UNIQUE NOT NULL, -- Phone number or IG ID
    platform_source VARCHAR(50) NOT NULL, -- 'whatsapp' | 'instagram'
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'customer', -- 'admin' | 'customer'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

-- Products Table
CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    paystack_reference VARCHAR(100),
    total_amount FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'paid' | 'synced'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat Sessions
CREATE TABLE chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    status VARCHAR(50) DEFAULT 'active',
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ
);

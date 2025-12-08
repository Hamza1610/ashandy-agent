# ASHY (Sabi) - AI Sales & Help Assistant

**Version:** 1.0  
**Date:** December 2025  
**Status:** Active Development

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Business Context](#business-context)
3. [System Architecture](#system-architecture)
4. [Technology Stack](#technology-stack)
5. [AI Models & Agents](#ai-models--agents)
6. [User Flow Diagram](#user-flow-diagram)
7. [Agentic Workflow](#agentic-workflow)
8. [API Endpoints](#api-endpoints)
9. [Database Schema](#database-schema)
10. [Environment Variables](#environment-variables)
11. [Installation & Setup](#installation--setup)
12. [Project Structure](#project-structure)
13. [Deployment Guide](#deployment-guide)
14. [Testing & QA](#testing--qa)
15. [Troubleshooting](#troubleshooting)

---

## 🎯 Executive Summary

ASHY is a **multimodal, agentic retail assistant** designed for cosmetics businesses. It bridges online browsing and in-store consultation through WhatsApp and Instagram, featuring:

- ✅ **Visual Search**: Upload product images for instant identification (SAM + DINOv3)
- ✅ **Semantic Memory**: Remembers customer preferences (skin type, budget, size)
- ✅ **Conversational AI**: Llama 4 Scout for personalized sales consultation
- ✅ **Payment Integration**: Automated Paystack payment links
- ✅ **POS Synchronization**: Real-time inventory sync with PHP Point of Sale
- ✅ **Safety Rails**: Llama Guard for input/output filtering
- ✅ **24/7 Availability**: Instant responses with semantic caching

---

## 🏢 Business Context

### Problem Statement

Retail businesses (especially cosmetics) face:
1. **High Latency**: Human agents can't respond 24/7 instantly
2. **Context Loss**: Customers repeat preferences every conversation
3. **Visual Disconnect**: Customers have product photos but can't describe them
4. **Safety Risks**: AI hallucinations and toxic content generation

### Target Users

**Primary User: "The Busy Shopper"**
- Values speed, shops on mobile
- Sends screenshots from Instagram/Pinterest asking "Do you have this?"
- Needs instant price checks and honest product advice

**Secondary User: "The Store Manager"**
- Tracks inventory and handles escalations
- Needs automated reporting and compliance tools

### Success Metrics (KPIs)

- **Conversion Rate**: % of payment links → successful transactions
- **Containment Rate**: % of queries handled without human handoff
- **Response Accuracy**: Weekly spot-check validation
- **Latency**: <1s cached, <5s LLM, <8s visual search

---

## 🏗️ System Architecture

![Alt text](https://res.cloudinary.com/dcq7l1xjn/image/upload/v1765201484/arch_ashy_nskrxc.png)


---

## 🔧 Technology Stack

### Backend Framework
- **FastAPI (Python 3.11+)**: Core REST API framework
  - High performance, automatic OpenAPI docs
  - Async support for webhooks
  - Type validation with Pydantic

### AI & Machine Learning

#### Language Models
- **Llama 4 Scout**: Primary conversational AI
  - Text-based sales consultation
  - Intent detection (order/query/handoff)
  - Context-aware recommendations

- **Llama Guard**: Safety middleware
  - Input filtering (jailbreaks, toxic prompts)
  - Output validation (hallucination prevention)
  - Compliance enforcement (NDPR)

#### Vision Models
- **SAM (Segment Anything Model)**: Image segmentation
  - Isolates products from user-uploaded images
  - Handles complex backgrounds

- **DINOv3**: Visual embeddings
  - Generates 768-dimensional product embeddings
  - Powers visual search matching

### Orchestration
- **LangGraph**: Multi-agent workflow orchestration
  - StateGraph for stateful conversations
  - Conditional routing (admin vs customer)
  - Tool invocation framework

- **LangSmith**: Observability & debugging
  - Trace agent runs
  - Monitor latency/errors
  - Production monitoring

### Databases & Storage

#### Relational Database
- **PostgreSQL 15+**: Primary structured data
  - Users, products, orders, chat sessions
  - JSONB for flexible metadata
  - ACID compliance for transactions

#### Vector Database
- **Pinecone**: Semantic search & memory
  - User memory vectors (384-dim for text embeddings)
  - Product embeddings (768-dim for visual search)
  - Fast similarity queries (<100ms)

#### Cache Layer
- **Redis**: High-speed caching
  - Semantic response cache (reduce LLM calls)
  - Session management
  - Rate limiting

### External Integrations

#### Messaging Platforms
- **WhatsApp Cloud API** (Meta)
  - Message/media handling
  - Template messages
  - Webhook verification

- **Instagram Graph API** (Meta)
  - DM processing
  - Comment auto-replies

#### Payment Gateway
- **Paystack API**
  - Payment link generation
  - Webhook confirmations
  - Transaction verification

#### POS System
- **PHP Point of Sale**: Local inventory system
  - Python connector script (polls MySQL)
  - Bidirectional sync (inventory + orders)
  - API bridge: `/api/v1/pos/*`

#### Utilities
- **Termii SMS**: Logistics fallback
- **FPDF**: Weekly PDF report generation

### Deployment
- **Docker**: Multi-container orchestration
  - App container (FastAPI + LangGraph)
  - PostgreSQL container
  - Redis container
  - Pinecone (cloud-managed)

- **Cloud Hosting**: Render/AWS/GCP
  - Auto-scaling
  - Health checks
  - 99.9% uptime SLA

---

## 🤖 AI Models & Agents

### Multi-Agent Architecture

ASHY uses **6 specialized agents** orchestrated by LangGraph:

#### 1. Router Agent
**Role**: Traffic controller and user classification

**Responsibilities**:
- Extract sender ID from webhook (wa_id/IG ID)
- Check admin whitelist (PostgreSQL `users` table)
- Classify query type (text vs image)
- Route to appropriate agent

**Tools Used**:
- Query PostgreSQL Tool
- Meta API Tool (for sender info)

**Decision Logic**:
```python
if sender_id in admin_whitelist:
    route_to(AdminAgent)
elif message.contains_image():
    route_to(VisualSearchAgent)
else:
    route_to(SafetyAgent)  # All customer queries pass through safety
```

---

#### 2. Safety Agent
**Role**: Input/output filtering and compliance

**Responsibilities**:
- Run Llama Guard on all customer messages
- Block toxic/harmful queries
- Log violations to `safety_logs` table
- Enforce NDPR data privacy

**Tools Used**:
- Run Llama Guard Tool
- Query PostgreSQL Tool (logging)

**Blocking Categories**:
- Jailbreak attempts
- Competitor mentions
- Toxic/abusive language
- Dangerous medical advice

**Output**: "Safe" (proceed) or "Blocked" (log and terminate)

---

#### 3. Visual Search Agent
**Role**: Image-based product identification

**Responsibilities**:
- Download image from Meta webhook
- Segment products using SAM
- Generate embeddings with DINOv3
- Query Pinecone for matches
- Retrieve product details from PostgreSQL

**Tools Used**:
- Run Visual Embedding Tool (SAM + DINO)
- Upsert/Query Pinecone Tool
- Query PostgreSQL Tool

**Process Flow**:
```
Image URL → SAM Segmentation → DINO Embedding (768-dim) 
→ Pinecone Similarity Search → Product Matches → Stock Check
```

**Performance**: <8 seconds end-to-end

---

#### 4. Sales Consultant Agent
**Role**: Conversational sales and recommendations

**Responsibilities**:
- Handle text-based queries (Llama 4 Scout)
- Retrieve user memory from Pinecone (preferences)
- Check semantic cache in Redis
- Generate personalized recommendations
- Detect order intent
- Trigger sentiment analysis for handoff

**Tools Used**:
- Query Pinecone Tool (user memory)
- Redis Cache Tool (semantic cache)
- Query PostgreSQL Tool (products/inventory)
- Sentiment Analysis Tool
- Send Message Tool (Meta API)

**Memory Recall Example**:
```
User: "I need something for dry skin"
Agent: [Queries Pinecone for user_id memory]
→ Finds: "skin_type: dry, budget: ₦5000, prefers serums"
Agent: "Based on your dry skin type, I recommend our Hydrating Serum (₦4500, in stock)"
```

**Semantic Caching**:
- Hash query embeddings
- Check Redis for similar queries (>0.9 similarity)
- Serve cached response if hit (<1s latency)

---

#### 5. Payment and Order Agent
**Role**: Transaction management and fulfillment

**Responsibilities**:
- Generate Paystack payment links
- Create orders in PostgreSQL
- Handle Paystack webhook confirmations
- Update order status (pending → paid → synced)
- Queue orders for POS injection
- Send confirmation messages

**Tools Used**:
- Generate Payment Link Tool (Paystack)
- Query PostgreSQL Tool (orders)
- Sync POS Tool (PHP POS Connector)
- Send Message Tool (confirmations)

**Order Lifecycle**:
```
1. Sales Agent detects intent → Payment Agent creates order
2. Generate Paystack link → Send to customer
3. Customer pays → Paystack webhook fires
4. Update order status → Queue for POS sync
5. Shop PC script confirms sync → Send logistics notification
```

---

#### 6. Admin Agent
**Role**: Manager commands and reporting

**Responsibilities**:
- Process admin commands (/stock, /report)
- Sync inventory via POS Connector
- Generate weekly PDF reports (FPDF)
- Clear caches and reindex vectors
- Manual override capabilities

**Tools Used**:
- Sync POS Tool (inventory updates)
- Generate Report Tool (FPDF)
- Redis Cache Tool (clear)
- Query Pinecone Tool (reindex)

**Admin Commands**:
- `/stock` - Trigger POS inventory sync
- `/report` - Generate weekly sales PDF
- `/cache clear` - Purge Redis semantic cache
- `/reindex` - Rebuild Pinecone embeddings

---

### Agent Collaboration Pattern

Agents share state via LangGraph's `StateGraph`:

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    session_id: str
    platform: str  # "whatsapp" or "instagram"
    query_type: str  # "text" or "image"
    is_admin: bool
    user_memory: Dict  # From Pinecone
    order_data: Optional[Dict]
    sentiment_score: Optional[float]
    cached_response: Optional[str]
```

**Execution Flow**:
1. Router Agent sets `is_admin`, `query_type`
2. Safety Agent validates and continues
3. Visual/Sales Agent processes and updates `order_data`
4. Payment Agent handles transactions
5. All agents log to shared state

---

## 📊 User Flow Diagram

```mermaid
flowchart TD
    A[Customer/Admin Sends Message on WhatsApp/Instagram] --> B{Platform?}
    B -->|WhatsApp| C[Webhook: /webhook/whatsapp]
    B -->|Instagram| D[Webhook: /webhook/instagram]
    
    C --> E{User Type?}
    D --> E
    
    E -->|Admin| F[Router Agent: Admin Path]
    E -->|Customer| G[Router Agent: Customer Path]
    
    F --> H[Admin Agent: Process Command]
    H --> I{Command Type?}
    I -->|/stock| J[Sync POS: Update Inventory]
    I -->|/report| K[Generate PDF Report]
    J --> L[Send Confirmation via Meta API]
    K --> L
    
    G --> M[Safety Agent: Llama Guard Filter]
    M -->|Blocked| N[Log Violation → End]
    M -->|Safe| O{Query Type?}
    
    O -->|Image| P[Visual Search Agent]
    P --> P1[SAM Segmentation]
    P1 --> P2[DINO Embedding]
    P2 --> P3[Pinecone Match]
    P3 --> Q[Retrieve Product Details]
    
    O -->|Text| R[Sales Consultant Agent]
    R --> R1{Check Redis Cache}
    R1 -->|Hit| R2[Serve Cached Response]
    R1 -->|Miss| R3[Query Pinecone User Memory]
    R3 --> R4[Llama 4 Scout Inference]
    R4 --> R5[Cache New Response]
    
    Q --> S[Sales Response with Product Info]
    R2 --> S
    R5 --> S
    
    S --> T{Order Intent?}
    T -->|No| U[Send Message via Meta API]
    T -->|Yes| V[Payment Agent: Generate Paystack Link]
    
    V --> W[Create Order in PostgreSQL]
    W --> X[Send Payment Link to Customer]
    X --> Y[Customer Pays]
    
    Y --> Z[Paystack Webhook: /webhook/paystack]
    Z --> AA[Update Order Status: paid]
    AA --> AB[Queue for POS Sync]
    AB --> AC[Shop PC Script Confirms Sync]
    AC --> AD[Send Confirmation Message]
    
    AD --> AE{Sentiment Check}
    U --> AE
    AE -->|Negative| AF[Alert Manager for Handoff]
    AE -->|Positive| AG[Update Chat Session → End]
    
    AF --> AG
    L --> AG
    N --> AG
```

**Key Flow Features**:
- **Dual Entry**: WhatsApp & Instagram webhooks
- **Admin Bypass**: Whitelisted users skip safety checks
- **Semantic Caching**: <1s responses for common queries
- **Visual Pipeline**: SAM → DINO → Pinecone (8s max)
- **Payment Loop**: Async webhook handling
- **Handoff Trigger**: Sentiment-based escalation

---

## 🔄 Agentic Workflow (LangGraph)

```mermaid
graph TD
    Start[Webhook Event: Meta/Paystack] --> Router[Router Agent Node]
    
    Router -->|Admin| Admin[Admin Agent Node]
    Router -->|Customer| Safety[Safety Agent Node]
    
    Admin --> AdminAction{Command Type}
    AdminAction -->|/stock| PosSync[POS Sync Tool]
    AdminAction -->|/report| Report[Generate Report Tool]
    PosSync --> AdminResp[Admin Response Node]
    Report --> AdminResp
    
    Safety -->|Blocked| Log[Safety Log Tool → END]
    Safety -->|Pass| Cache[Cache Check Node]
    
    Cache -->|Hit| CachedResp[Serve Cached Response]
    Cache -->|Miss| QueryType{Query Type Router}
    
    QueryType -->|Image| Visual[Visual Search Agent Node]
    QueryType -->|Text| Memory[Memory Retrieval Node]
    
    Visual --> VisualTools[SAM Tool → DINO Tool → Pinecone Query]
    VisualTools --> ProductFetch[PostgreSQL Product Tool]
    
    Memory --> MemTools[Pinecone User Memory Query]
    MemTools --> Sales[Sales Consultant Agent Node]
    
    Sales --> LlamaInf[Llama 4 Scout Inference]
    LlamaInf --> CacheUpdate[Redis Cache Update Tool]
    
    ProductFetch --> Response[Response Composition Node]
    CacheUpdate --> Response
    CachedResp --> Response
    
    Response --> Intent{Order Intent?}
    Intent -->|No| Send[Meta API Send Tool]
    Intent -->|Yes| Payment[Payment Agent Node]
    
    Payment --> PayTools[Paystack Generate Link Tool]
    PayTools --> OrderDB[PostgreSQL Order Insert Tool]
    OrderDB --> SendLink[Meta API Send Tool]
    
    SendLink --> WebhookWait[Async: Wait for Paystack Webhook]
    WebhookWait --> OrderUpdate[PostgreSQL Order Update Tool]
    OrderUpdate --> PosQueue[POS Sync Queue Tool]
    PosQueue --> Confirm[Send Confirmation Tool]
    
    Send --> Sentiment[Sentiment Analysis Tool]
    Confirm --> Sentiment
    
    Sentiment -->|Negative| Handoff[Alert Manager Tool]
    Sentiment -->|Positive| EndNode[Update Chat Session → END]
    
    AdminResp --> EndNode
    Handoff --> EndNode
    Log --> EndNode
    
    style Start fill:#e1f5ff
    style EndNode fill:#ffe1e1
    style Safety fill:#fff4e1
    style Visual fill:#e1ffe1
    style Sales fill:#e1ffe1
    style Payment fill:#ffe1f5
```

**LangGraph Implementation Details**:

### State Schema
```python
from typing import TypedDict, Annotated, List, Dict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class ASHYState(TypedDict):
    # Core conversation
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    session_id: str
    platform: str  # "whatsapp" | "instagram"
    
    # Routing
    is_admin: bool
    query_type: str  # "text" | "image" | "admin_command"
    
    # Memory & context
    user_memory: Optional[Dict]  # From Pinecone
    cached_response: Optional[str]
    
    # Processing
    image_url: Optional[str]
    visual_matches: Optional[List[Dict]]
    product_recommendations: Optional[List[Dict]]
    
    # Order management
    order_intent: bool
    order_data: Optional[Dict]
    paystack_reference: Optional[str]
    
    # Sentiment & handoff
    sentiment_score: Optional[float]
    requires_handoff: bool
    
    # Admin
    admin_command: Optional[str]
```

### Conditional Edges
```python
def route_after_router(state: ASHYState):
    if state["is_admin"]:
        return "admin_agent"
    else:
        return "safety_agent"

def route_after_safety(state: ASHYState):
    if state.get("blocked", False):
        return "end"
    else:
        return "cache_check"

def route_query_type(state: ASHYState):
    if state["query_type"] == "image":
        return "visual_agent"
    else:
        return "memory_retrieval"

def route_order_intent(state: ASHYState):
    if state["order_intent"]:
        return "payment_agent"
    else:
        return "send_response"
```

### Graph Construction
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Initialize graph
workflow = StateGraph(state_schema=ASHYState)

# Add nodes (agents)
workflow.add_node("router", router_agent_node)
workflow.add_node("safety", safety_agent_node)
workflow.add_node("admin", admin_agent_node)
workflow.add_node("cache_check", cache_check_node)
workflow.add_node("visual", visual_search_agent_node)
workflow.add_node("memory", memory_retrieval_node)
workflow.add_node("sales", sales_consultant_agent_node)
workflow.add_node("payment", payment_agent_node)
workflow.add_node("response", response_node)

# Add edges
workflow.add_edge(START, "router")
workflow.add_conditional_edges("router", route_after_router)
workflow.add_conditional_edges("safety", route_after_safety)
workflow.add_conditional_edges("cache_check", lambda s: "response" if s.get("cached_response") else "query_router")
workflow.add_conditional_edges("query_router", route_query_type)
workflow.add_edge("visual", "response")
workflow.add_edge("memory", "sales")
workflow.add_edge("sales", "response")
workflow.add_conditional_edges("response", route_order_intent)
workflow.add_edge("payment", END)
workflow.add_edge("admin", END)

# Compile with persistence
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

### Tool Integration
Each agent node invokes tools via LangChain:

```python
from langchain.tools import tool

@tool
def query_postgresql(query: str, params: Dict = None) -> List[Dict]:
    """Execute SQL query on PostgreSQL database."""
    # Implementation using SQLAlchemy
    pass

@tool
def query_pinecone(namespace: str, vector: List[float], top_k: int = 5) -> List[Dict]:
    """Query Pinecone for similar vectors."""
    # Implementation using pinecone-client
    pass

@tool
def run_sam_dino(image_url: str) -> Dict:
    """Process image with SAM and DINO."""
    # Download image, run SAM segmentation, DINO embedding
    pass
```

### Execution Example
```python
# Invoke workflow
config = {"configurable": {"thread_id": "session-123"}}
input_state = {
    "messages": [{"role": "user", "content": "Do you have red lipstick?"}],
    "user_id": "wa-2341234567890",
    "platform": "whatsapp"
}

result = app.invoke(input_state, config)
# Returns final state with response message
```

---

## 🌐 API Endpoints

**Base URL**: `https://ashy-api.render.com` (or your deployment URL)

### 1. System & Health

#### GET `/health`
**Purpose**: Docker/Render health check

**Response**:
```json
{
  "status": "healthy",
  "services": {
    "db": "up",
    "redis": "up",
    "pinecone": "up"
  }
}
```

#### GET `/`
**Purpose**: Root endpoint

**Response**:
```json
{
  "message": "Sabi API v1.0 is running",
  "version": "1.0.0"
}
```

---

### 2. Webhooks (External Events)

#### GET `/webhook/whatsapp`
**Purpose**: Meta Cloud API verification challenge

**Query Parameters**:
- `hub.mode`: "subscribe"
- `hub.verify_token`: Your verification token
- `hub.challenge`: Random string to echo back

**Response**: Echo `hub.challenge` value

---

#### POST `/webhook/whatsapp`
**Purpose**: Main entry point for WhatsApp messages

**Headers**:
- `Content-Type`: application/json

**Request Body**:
```json
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "2341234567890",
          "id": "wamid.XXX",
          "type": "text",
          "text": {"body": "Do you have red lipstick?"}
        }]
      }
    }]
  }]
}
```

**Logic Flow**:
1. Extract `wa_id` (sender phone number)
2. Check admin whitelist in PostgreSQL
3. Route to Admin/Sales Controller
4. Return 200 OK immediately (Meta requirement)

**Response**: `200 OK` (empty body)

---

#### POST `/webhook/instagram`
**Purpose**: Instagram DMs and comments

**Request Body**:
```json
{
  "entry": [{
    "messaging": [{
      "sender": {"id": "instagram_user_id"},
      "message": {"text": "Price check?"}
    }]
  }]
}
```

**Response**: `200 OK`

---

#### POST `/webhook/paystack`
**Purpose**: Payment success events

**Headers**:
- `x-paystack-signature`: HMAC SHA-512 signature

**Request Body**:
```json
{
  "event": "charge.success",
  "data": {
    "reference": "order-uuid-123",
    "amount": 500000,
    "status": "success"
  }
}
```

**Actions**:
1. Verify signature with Paystack secret
2. Find order in DB by reference
3. Update status to `paid`
4. Trigger POS sync queue
5. Send confirmation message

**Response**: `200 OK`

---

### 3. POS Connector API (The Bridge)

**Security**: All endpoints require `X-API-KEY` header

#### POST `/api/v1/pos/sync/inventory`
**Purpose**: Receive stock updates from shop PC

**Headers**:
- `X-API-KEY`: Your POS connector secret

**Request Body**:
```json
[
  {
    "phppos_item_id": 101,
    "sku": "SERUM-01",
    "qty": 45,
    "price": 5000,
    "name": "Hydrating Serum",
    "category": "Skincare"
  },
  {
    "phppos_item_id": 102,
    "sku": "NIVEA-BL",
    "qty": 12,
    "price": 2500,
    "name": "Nivea Body Lotion"
  }
]
```

**Actions**:
- Bulk upsert into `products` table
- Update `inventory_cache`
- Trigger Pinecone reindexing if needed

**Response**:
```json
{
  "success": true,
  "updated": 2,
  "message": "Inventory synced successfully"
}
```

---

#### GET `/api/v1/pos/orders/pending`
**Purpose**: Shop PC queries for new online sales

**Headers**:
- `X-API-KEY`: Your POS connector secret

**Response**:
```json
[
  {
    "order_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "wa-2341234567890",
    "items": [
      {"sku": "SERUM-01", "qty": 1, "price": 5000}
    ],
    "total": 5000,
    "created_at": "2025-12-08T10:30:00Z"
  }
]
```

---

#### POST `/api/v1/pos/orders/{order_id}/confirm`
**Purpose**: Shop PC confirms order recorded in local POS

**Headers**:
- `X-API-KEY`: Your POS connector secret

**Request Body**:
```json
{
  "phppos_sale_id": 789,
  "status": "synced"
}
```

**Actions**:
- Update order status to `synced_to_pos`
- Store `phppos_sale_id` in order record

**Response**:
```json
{
  "success": true,
  "message": "Order confirmed in POS"
}
```

---

### 4. Admin Utilities (Internal)

**Security**: Requires `X-ADMIN-API-KEY` header

#### POST `/api/v1/admin/cache/clear`
**Purpose**: Force clear Redis semantic cache

**Headers**:
- `X-ADMIN-API-KEY`: Admin secret

**Response**:
```json
{
  "success": true,
  "message": "Cache cleared",
  "keys_deleted": 1234
}
```

---

#### POST `/api/v1/admin/vector/reindex`
**Purpose**: Rebuild Pinecone embeddings

**Headers**:
- `X-ADMIN-API-KEY`: Admin secret

**Request Body**:
```json
{
  "namespace": "product_embeddings",
  "batch_size": 100
}
```

**Actions**:
- Query all products from PostgreSQL
- Regenerate embeddings with DINO
- Upsert to Pinecone

**Response**:
```json
{
  "success": true,
  "message": "Reindexing started",
  "total_products": 450
}
```

---

## 🗄️ Database Schema

### PostgreSQL Tables

#### 1. users
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id VARCHAR(255) UNIQUE NOT NULL,  -- WhatsApp/IG ID
    platform_source VARCHAR(50) NOT NULL,      -- 'whatsapp' | 'instagram'
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'customer',       -- 'customer' | 'admin'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_platform_id ON users(platform_id);
CREATE INDEX idx_users_role ON users(role);
```

#### 2. products
```sql
CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phppos_item_id INT UNIQUE,                 -- Foreign key to PHP POS
    barcode VARCHAR(100),
    sku VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    category VARCHAR(100),
    image_url TEXT,
    metadata JSONB,                            -- Flexible attributes
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_phppos ON products(phppos_item_id);
```

#### 3. chat_sessions
```sql
CREATE TABLE chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active'        -- 'active' | 'closed' | 'handed_off'
);

CREATE INDEX idx_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_sessions_status ON chat_sessions(status);
```

#### 4. chat_messages
```sql
CREATE TABLE chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(session_id),
    sender_type VARCHAR(20) NOT NULL,          -- 'user' | 'agent' | 'admin'
    content TEXT,
    image_url TEXT,
    sentiment_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON chat_messages(session_id);
CREATE INDEX idx_messages_sentiment ON chat_messages(sentiment_score);
```

#### 5. orders
```sql
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    paystack_reference VARCHAR(100),
    phppos_sale_id INT,                        -- Synced sale ID
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',      -- 'pending' | 'paid' | 'synced_to_pos' | 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_paystack ON orders(paystack_reference);
```

#### 6. safety_logs
```sql
CREATE TABLE safety_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    prompt_text TEXT,
    violation_category VARCHAR(100),           -- 'toxic' | 'jailbreak' | 'competitor_mention'
    action_taken VARCHAR(50) DEFAULT 'blocked',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_safety_user ON safety_logs(user_id);
CREATE INDEX idx_safety_category ON safety_logs(violation_category);
```

---

### Pinecone Indexes

#### 1. user-semantic-memory
**Purpose**: Store user preferences and context

**Configuration**:
- **Dimension**: 384 (text embeddings)
- **Metric**: cosine
- **Pods**: Starter (1 pod)

**Vector Structure**:
```python
{
    "id": "user-wa-2341234567890-memory-1",
    "values": [0.123, -0.456, ...],  # 384-dim
    "metadata": {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "memory_text": "Customer prefers serums, has dry skin, budget ₦5000",
        "created_at": "2025-12-08T10:30:00Z"
    }
}
```

**Query Example**:
```python
index.query(
    vector=[0.123, ...],
    top_k=3,
    include_metadata=True,
    filter={"user_id": "550e8400-..."}
)
```

---

#### 2. product-embeddings
**Purpose**: Visual search index for product matching

**Configuration**:
- **Dimension**: 768 (visual embeddings from DINOv3)
- **Metric**: cosine
- **Pods**: Starter (1 pod, scale as needed)

**Vector Structure**:
```python
{
    "id": "product-550e8400-e29b-41d4-a716-446655440001",
    "values": [0.789, -0.234, ...],  # 768-dim
    "metadata": {
        "product_id": "550e8400-e29b-41d4-a716-446655440001",
        "sku": "SERUM-01",
        "name": "Hydrating Serum",
        "price": 5000,
        "category": "Skincare",
        "embedding_type": "visual_clip"
    }
}
```

**Query Example** (visual search):
```python
# After generating DINO embedding from uploaded image
index.query(
    vector=dino_embedding,  # 768-dim
    top_k=5,
    include_metadata=True,
    filter={"category": "Skincare"}
)
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```bash
# ============================================
# APPLICATION SETTINGS
# ============================================
APP_NAME=ASHY
APP_VERSION=1.0.0
ENVIRONMENT=production  # development | staging | production
DEBUG=False
LOG_LEVEL=INFO

# ============================================
# DATABASE - PostgreSQL
# ============================================
DATABASE_URL=postgresql://user:password@localhost:5432/ashy_db
# For async: postgresql+asyncpg://user:password@host:port/db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# ============================================
# VECTOR DATABASE - Pinecone
# ============================================
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-west1-gcp  # Your Pinecone region
PINECONE_INDEX_USER_MEMORY=user-semantic-memory
PINECONE_INDEX_PRODUCTS=product-embeddings

# ============================================
# CACHE - Redis
# ============================================
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password  # Optional
REDIS_CACHE_TTL=3600  # 1 hour in seconds

# ============================================
# META PLATFORMS - WhatsApp Cloud API
# ============================================
META_WHATSAPP_TOKEN=your-whatsapp-access-token
META_WHATSAPP_PHONE_ID=your-phone-number-id
META_WHATSAPP_BUSINESS_ID=your-business-account-id
META_VERIFY_TOKEN=your-custom-verify-token  # For webhook verification

# ============================================
# META PLATFORMS - Instagram Graph API
# ============================================
META_INSTAGRAM_TOKEN=your-instagram-access-token
META_INSTAGRAM_ACCOUNT_ID=your-ig-business-account-id

# ============================================
# PAYMENT GATEWAY - Paystack
# ============================================
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxxxxxxxxx
PAYSTACK_WEBHOOK_SECRET=your-paystack-webhook-secret

# ============================================
# PHP POS CONNECTOR
# ============================================
POS_CONNECTOR_API_KEY=your-secure-pos-api-key
POS_LOCAL_MYSQL_HOST=localhost  # For local sync script
POS_LOCAL_MYSQL_USER=phppos_user
POS_LOCAL_MYSQL_PASSWORD=phppos_password
POS_LOCAL_MYSQL_DATABASE=phppos_db
POS_SYNC_INTERVAL=300  # 5 minutes in seconds

# ============================================
# AI MODELS - Llama (Meta AI)
# ============================================
LLAMA_API_KEY=your-meta-ai-api-key
LLAMA_MODEL_SCOUT=llama-4-scout  # For conversational AI
LLAMA_MODEL_GUARD=llama-guard-2  # For safety filtering

# ============================================
# AI MODELS - Vision (SAM + DINO)
# ============================================
SAM_MODEL_PATH=/models/sam_vit_h.pth
DINO_MODEL_PATH=/models/dinov3_vitl14.pth
DINO_EMBEDDING_DIM=768

# ============================================
# LANGGRAPH & LANGSMITH
# ============================================
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=ashy-production
LANGCHAIN_TRACING_V2=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# ============================================
# ADMIN SETTINGS
# ============================================
ADMIN_WHITELIST=2341234567890,2349876543210  # Comma-separated phone numbers
ADMIN_API_KEY=your-secure-admin-api-key

# ============================================
# LOGISTICS - Termii SMS Fallback
# ============================================
TERMII_API_KEY=your-termii-api-key
TERMII_SENDER_ID=ASHY

# ============================================
# SECURITY
# ============================================
SECRET_KEY=your-super-secret-key-min-32-chars
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# ============================================
# DEPLOYMENT
# ============================================
BASE_URL=https://ashy-api.render.com
WEBHOOK_BASE_URL=https://ashy-api.render.com/webhook
```

---

## 🚀 Installation & Setup

### Prerequisites

- **Python**: 3.11+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **PostgreSQL**: 15+ (or use Docker)
- **Redis**: 7+ (or use Docker)
- **Git**: For version control

---

### Local Development Setup

#### 1. Clone Repository
```bash
git clone https://github.com/your-org/ashy-sabi.git
cd ashy-sabi
```

#### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Key Dependencies** (`requirements.txt`):
```txt
# Core Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.25
asyncpg==0.29.0
psycopg2-binary==2.9.9
alembic==1.13.1

# Vector Database
pinecone-client==3.0.0

# Cache
redis==5.0.1
hiredis==2.3.2

# AI & ML
langchain==0.1.0
langgraph==0.0.30
langsmith==0.0.80
transformers==4.36.0
torch==2.1.2
torchvision==0.16.2

# Meta APIs
requests==2.31.0
httpx==0.26.0

# Payment
paystack==1.0.3

# Image Processing
Pillow==10.2.0
opencv-python==4.9.0.80

# Reports
fpdf2==2.7.8

# Utilities
python-dotenv==1.0.0
python-multipart==0.0.6
```

#### 4. Configure Environment
```bash
cp config/.env.example .env
# Edit .env with your credentials
```

#### 5. Initialize Database
```bash
# Run migrations
alembic upgrade head

# Seed initial data (admin users, sample products)
python scripts/seed_data.py
```

#### 6. Start Services with Docker Compose
```bash
docker-compose up -d
```

**`docker-compose.yml`**:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ashy_user
      POSTGRES_PASSWORD: ashy_password
      POSTGRES_DB: ashy_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./app:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
  redis_data:
```

#### 7. Run Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 8. Verify Setup
```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

---

### POS Connector Script Setup

On the **shop PC** (local machine with PHP POS):

#### 1. Install Python Dependencies
```bash
pip install pymysql requests schedule
```

#### 2. Configure Script
Edit `scripts/pos_local_sync.py`:
```python
# POS Database Config
POS_DB_CONFIG = {
    'host': 'localhost',
    'user': 'phppos_user',
    'password': 'phppos_password',
    'database': 'phppos_db'
}

# Cloud API Config
CLOUD_API_URL = 'https://ashy-api.render.com/api/v1/pos'
API_KEY = 'your-secure-pos-api-key'
```

#### 3. Run Script
```bash
python scripts/pos_local_sync.py
```

**Script automatically**:
- Polls PHP POS MySQL every 5 minutes
- Syncs inventory changes to cloud
- Fetches pending online orders
- Confirms order injections

---

## 📁 Project Structure

```
ashy-sabi/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry point
│   ├── agents/                      # LangGraph agents
│   │   ├── __init__.py
│   │   ├── router_agent.py
│   │   ├── safety_agent.py
│   │   ├── visual_search_agent.py
│   │   ├── sales_consultant_agent.py
│   │   ├── payment_order_agent.py
│   │   └── admin_agent.py
│   ├── tools/                       # LangChain tools
│   │   ├── __init__.py
│   │   ├── db_tools.py
│   │   ├── vector_tools.py
│   │   ├── cache_tools.py
│   │   ├── meta_api_tools.py
│   │   ├── paystack_tools.py
│   │   ├── pos_connector_tools.py
│   │   ├── visual_tools.py
│   │   ├── llama_guard_tool.py
│   │   ├── sentiment_tool.py
│   │   └── report_tool.py
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── main_workflow.py         # LangGraph StateGraph
│   ├── models/
│   │   ├── __init__.py
│   │   ├── db_models.py             # SQLAlchemy schemas
│   │   ├── api_models.py            # Pydantic models
│   │   └── agent_states.py          # LangGraph state
│   ├── routers/                     # FastAPI endpoints
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── webhooks.py
│   │   ├── pos_connector.py
│   │   └── admin.py
│   ├── services/                    # Business logic
│   │   ├── __init__.py
│   │   ├── meta_service.py
│   │   ├── paystack_service.py
│   │   ├── pos_service.py
│   │   ├── ai_service.py
│   │   ├── db_service.py
│   │   ├── vector_service.py
│   │   ├── cache_service.py
│   │   └── report_service.py
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       ├── logging.py
│       ├── auth.py
│       └── embedding_utils.py
├── config/
│   ├── .env.example
│   └── settings.py
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── render.yaml
├── scripts/
│   ├── pos_local_sync.py
│   ├── db_migrate.py
│   └── seed_data.py
├── tests/
│   ├── test_agents.py
│   ├── test_endpoints.py
│   ├── test_tools.py
│   └── test_integrations.py
├── docs/
│   ├── README.md
│   ├── api_spec.md
│   ├── db_schema.sql
│   └── architecture_diagram.png
├── .gitignore
├── requirements.txt
└── README.md                        # This file
```

---

## 🌐 Deployment Guide

### Option 1: Render (Recommended for Hackathon)

#### 1. Create Render Account
Sign up at [render.com](https://render.com)

#### 2. Create PostgreSQL Database
- Go to "New +" → "PostgreSQL"
- Name: `ashy-db`
- Plan: Free tier (sufficient for testing)
- Copy connection string

#### 3. Create Redis Instance
- Go to "New +" → "Redis"
- Name: `ashy-cache`
- Plan: Free tier
- Copy connection string

#### 4. Create Web Service
- Go to "New +" → "Web Service"
- Connect GitHub repository
- Configuration:
  - **Name**: ashy-api
  - **Environment**: Python 3
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - **Plan**: Starter ($7/month) or Free

#### 5. Add Environment Variables
In Render dashboard, add all variables from `.env` file

#### 6. Deploy
- Click "Create Web Service"
- Automatic deploys on git push

---

### Option 2: Docker Deployment

#### 1. Build Image
```bash
docker build -t ashy-api:latest .
```

**`Dockerfile`**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY config/ ./config/

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. Run Container
```bash
docker run -d \
  --name ashy-api \
  -p 8000:8000 \
  --env-file .env \
  ashy-api:latest
```

#### 3. Use Docker Compose (Multi-Container)
```bash
docker-compose -f deployment/docker-compose.yml up -d
```

---

## 🧪 Testing & QA

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agents.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Integration Tests

```bash
# Test webhooks
pytest tests/test_endpoints.py::test_whatsapp_webhook -v

# Test POS sync
pytest tests/test_integrations.py::test_pos_inventory_sync -v
```

### Red-Team Testing (Safety)

```bash
# Test jailbreak attempts
python tests/adversarial/test_jailbreaks.py

# Test toxic input filtering
python tests/adversarial/test_toxic_inputs.py
```

**Example Test**:
```python
# tests/test_agents.py
import pytest
from app.agents.safety_agent import safety_agent_node
from app.models.agent_states import ASHYState

def test_safety_agent_blocks_toxic():
    state = ASHYState(
        messages=[{"role": "user", "content": "You stupid bot"}],
        user_id="test-user"
    )
    result = safety_agent_node(state)
    assert result.get("blocked") == True
    assert "toxic" in result.get("violation_category")
```

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. Webhook Not Receiving Messages
**Problem**: WhatsApp/Instagram webhooks return 200 but no processing

**Solutions**:
- Verify webhook URL in Meta developer dashboard
- Check `META_VERIFY_TOKEN` matches
- Ensure public HTTPS URL (use ngrok for local testing)
- Check firewall/Render logs

```bash
# Test with ngrok
ngrok http 8000
# Update Meta webhook URL to ngrok URL
```

---

#### 2. Pinecone Connection Errors
**Problem**: `PineconeException: Index not found`

**Solutions**:
```bash
# Verify index exists
python -c "import pinecone; pinecone.init(api_key='...'); print(pinecone.list_indexes())"

# Create index if missing
python scripts/create_pinecone_indexes.py
```

---

#### 3. POS Sync Not Working
**Problem**: Inventory not updating from PHP POS

**Solutions**:
- Check `pos_local_sync.py` is running on shop PC
- Verify MySQL credentials
- Check API key in script matches cloud `.env`
- Review logs: `tail -f logs/pos_sync.log`

---

#### 4. High Latency (>10s responses)
**Problem**: Slow agent responses

**Solutions**:
- Check Redis cache hit rate: `redis-cli INFO stats`
- Optimize Pinecone queries (reduce `top_k`)
- Use semantic caching more aggressively
- Scale Pinecone pods (upgrade plan)

---

#### 5. Llama Guard False Positives
**Problem**: Safe queries being blocked

**Solutions**:
- Adjust Guard threshold in `app/tools/llama_guard_tool.py`
- Add whitelist patterns
- Review `safety_logs` table for patterns
- Fine-tune Guard prompts

---

## 📊 Monitoring & Analytics

### LangSmith Dashboard
- URL: https://smith.langchain.com
- View agent traces, latencies, errors
- Set up alerts for failures

### Key Metrics to Track
1. **Conversion Rate**: Orders/Payment Links
2. **Containment Rate**: (Total Queries - Handoffs) / Total Queries
3. **Cache Hit Rate**: Redis hits / Total queries
4. **Average Latency**: By agent type
5. **Safety Violations**: Daily count by category

---

## 🔒 Security Best Practices

1. **API Keys**: Never commit to git, use environment variables
2. **Webhook Signatures**: Always verify Paystack signatures
3. **Rate Limiting**: Implement for webhooks (use Redis)
4. **Input Validation**: Pydantic models for all endpoints
5. **HTTPS Only**: Enforce SSL for production
6. **Admin Whitelist**: Regularly audit admin phone numbers
7. **Database Backups**: Daily automated backups (Render handles this)

---

## 📝 Next Steps

### Phase 1: MVP (Week 1)
- [x] Setup infrastructure (DB, Redis, Pinecone)
- [x] Implement Router & Safety agents
- [x] Basic WhatsApp webhook integration
- [ ] Deploy to Render staging

### Phase 2: Core Features (Week 2)
- [ ] Visual Search agent (SAM + DINO)
- [ ] Sales Consultant agent (Llama 4)
- [ ] Semantic memory integration
- [ ] Payment flow (Paystack)

### Phase 3: Polish (Week 3)
- [ ] POS connector script
- [ ] Admin commands
- [ ] PDF reporting
- [ ] Red-team testing

### Phase 4: Production (Week 4)
- [ ] Load testing
- [ ] Production deployment
- [ ] Documentation finalization
- [ ] Training materials

---

## 📞 Support & Contact

- **Project Lead**: [Your Name]
- **Email**: contact@ashy-ai.com
- **Slack**: #ashy-dev
- **Issues**: [GitHub Issues](https://github.com/your-org/ashy-sabi/issues)

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Meta AI**: Llama models
- **Anthropic**: Claude for development assistance
- **LangChain**: LangGraph framework
- **Segment Anything**: SAM model
- **DINOv3**: Visual embeddings

---

**Last Updated**: December 8, 2025  
**Document Version**: 1.0.0
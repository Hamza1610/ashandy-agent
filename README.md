# 🌸 Awéléwà: The AI Sales & Logistics Agent
> **Winner of the Meta AI Developer Academy Hackathon 2025 (Loading...)**

![Status](https://img.shields.io/badge/Status-Active_Development-green)
![Version](https://img.shields.io/badge/Version-2.0_(Micro--Refactored)-blue)
![Tech](https://img.shields.io/badge/Stack-FastAPI_%7C_LangGraph_%7C_Llama_4_%7C_PostgreSQL-blueviolet)

**Awéléwà** (Yoruba for *"Beauty has come home"*) is a High-Agency AI system designed to solve "Retail Amnesia" for African MSMEs. 

**v2.0 Refactor:** The system now operates on a **Supervisor-Planner-Worker** architecture, giving it the ability to reason, plan, and execute complex multi-step workflows (e.g., *"Check the price of Ringlight, if under 30k, send payment link, then schedule delivery to Lekki"*).

---

## 🎯 Executive Summary

Retail businesses in Nigeria suffer from three core problems:
1.  **Ghost Stock:** Online payments for items that are physically out of stock.
2.  **Retail Amnesia:** Agents forget customer preferences.
3.  **Logistics Chaos:** Manual calculation of delivery fees leads to losses.

**Awéléwà solves this by:**
*   **Seeing:** Identifies products from user photos using **Llama 4 Vision**.
*   **Planning:** Decomposes complex user requests into executable steps using a **Planner Brain**.
*   **Delivering:** Automatically calculates zone-based delivery fees and dispatches riders using **Twilio**.

---

## 🏗️ v2.0 Architecture: The Team

Awéléwà uses **LangGraph** to orchestrate a team of specialized AI Agents. It mimics a real-world company structure:

### 1. 🛡️ The Supervisor (`supervisor_agent.py`)
*   **Role:** The Gatekeeper.
*   **Responsibilities:**
    *   **Input Guardrail:** Uses **Meta Llama Guard 4** to filter toxic/unsafe content.
    *   **Anti-Spam:** Detects low-value messages (e.g., "lol", emojis) and blocks them instantly locally (Regex).
    *   **Instant Feedback:** Sends **"Read Receipts" (Blue Ticks)** via Meta API immediately to reduce perceived latency.
    *   **Handoff:** Detects explicit requests for a "Human Manager".

### 2. 🧠 The Planner (`planner_agent.py`)
*   **Role:** The Brain / Manager.
*   **Responsibilities:**
    *   **Task Decomposition:** Breaks down user intent (e.g., "I want to buy X") into steps (`check_stock` -> `calculate_delivery` -> `request_approval` -> `generate_link`).
    *   **Business Rules:** Enforces critical logic:
        *   **Approval Rule:** Orders > ₦25,000 require Admin approval.
        *   **Visual Rule:** Images trigger Visual Analysis.
        *   **Inventory Truth:** Never sell what you haven't checked.

### 3. The Workers (Execution Layer)
Simple, specialized agents that "do as they are told".
*   **👷 Sales Worker (`sales_worker.py`):** Handles chat, product search, and **Visual Analysis** (Llama Vision).
*   **🛡️ Admin Worker (`admin_worker.py`):** Executes commands (`/sync`, `/stock`), generates reports, and handles approvals.
*   **💳 Payment Worker (`payment_worker.py`):** Calculates delivery fees and generates **Paystack** links.

---

## 📂 Comprehensive Codebase Structure

### `/app` (Core Application)
#### `/agents` (The Nodes)
*   **`supervisor_agent.py`:** Entry point. Handles safety & filtering.
*   **`planner_agent.py`:** The LLM Brain. Generates the Execution Plan.
*   **`sales_worker.py`:** Customer-facing worker. Bound to Product & Visual tools.
*   **`admin_worker.py`:** Internal worker. Bound to Reporting & Inventory tools.
*   **`payment_worker.py`:** Transaction worker. Bound to Paystack & Delivery tools.

#### `/workflows` (The Wiring)
*   **`main_workflow.py`:** Contains the **LangGraph** definition. Wires the Supervisor -> Planner -> Worker loops and defines conditional routing logic.

#### `/models` (Data Structures)
*   **`agent_states.py`:** Defines the `AgentState` schema (Plan, Messages, UserContext).
*   **`db_models.py`:** SQL Alchemy models (Products, Orders, Customers).
*   **`webhook_schemas.py`:** Pydantic models for Meta/Paystack webhooks.

#### `/services` (External Integrations)
*   **`meta_service.py`:** Handles WhatsApp/Instagram sending & Read Receipts.
*   **`ingestion_service.py`:** Logic for syncing Instagram posts to Inventory.
*   **`vector_service.py`:** Wrapper for Pinecone (Semantic Search).
*   **`cache_service.py`:** Wrapper for Redis (Semantic Caching).
*   **`paystack_service.py`:** Verification & Link Generation.

#### `/tools` (Agent Capabilities)
*   **`visual_tools.py`:** **Llama Vision** (OCR/Description) & **DINOv2** (Similarity).
*   **`product_tools.py`:** Search logic (Text & Vector).
*   **`pos_connector_tools.py`:** Sync logic for PHPPOS.
*   **`llama_guard_tool.py`:** Safety classifier.
*   **`memory_tools.py`:** Saving/Retrieving user preferences.
*   **`reporting_tools.py`:** Admin report generation.

### `/scripts` (Utilities)
*   **`ingest_instagram.py`:** Standalone script to sync IG posts to DB.
*   **`ingest_phppos.py`:** Initial inventory load from CSV/POS.
*   **`test_graph.py`:** CLI tool to simulate agent conversations without WhatsApp.
*   **`clear_cache.py`:** Utilities to wipe Redis/Pinecone for testing.

---

## 🔧 Configuration (.env)

Ensure these variables are set in your `.env` file:

```ini
# --- LLM & AI (Multi-Provider Failover) ---
LLAMA_API_KEY=gsk_...                   # Groq (Primary)
TOGETHER_API_KEY=...                     # Together AI (Fallback 1) - Optional
OPENROUTER_API_KEY=...                   # OpenRouter (Fallback 2) - Optional
HUGGINGFACE_API_KEY=hf_...               # HuggingFace (for DINOv2 embeddings)

# --- DATABASE ---
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ashandy
PINECONE_API_KEY=pc_...
PINECONE_ENV=us-east-1
PINECONE_INDEX_NAME=ashandy-index
REDIS_URL=redis://localhost:6379/0

# --- META (WHATSAPP/INSTAGRAM) ---
META_WHATSAPP_TOKEN=EAAG...
META_WHATSAPP_PHONE_ID=324...
META_INSTAGRAM_TOKEN=IGQ...
META_INSTAGRAM_ACCOUNT_ID=178...
META_VERIFY_TOKEN=ashandy_verification_token  # For Webhook handshake

# --- PAYMENTS & LOGISTICS ---
PAYSTACK_SECRET_KEY=sk_test_...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# --- ADMIN ---
ADMIN_PHONE_NUMBERS=["+23480...", "+23490..."]
```

> **💡 LLM Failover:** The system automatically falls back to Together AI → OpenRouter if Groq is unavailable. Check provider health at `/health/llm`.

---

## 🏃‍♂️ How to Run

### 1. Local Development
```bash
# Start the FastAPI Server
uvicorn app.main:app --reload --port 8000
```

### 2. Testing the Graph (CLI)
You can chat with the agent in your terminal without using WhatsApp:
```bash
python scripts/test_graph.py
```

### 3. Syncing Inventory
To pull the latest posts from Instagram into the product database:
```bash
python scripts/ingest_instagram.py
```
*Note: This can also be triggered via WhatsApp by an Admin sending `/sync_instagram`.*

---

## 🧪 Key Workflows

### 1. The "High Value" Check
*   **User:** "I want 3 wigs (Total 75k)."
*   **Planner:** "Total > 25k. Trigger Approval."
*   **Action:** Agent sends "Please wait for manager approval." -> Manager receives WhatsApp notification -> Manager Approves -> Agent sends Payment Link.

### 2. The Visual Search
*   **User:** Sends photo of a serum.
*   **Supervisor:** "Image detected."
*   **Planner:** "Assign Visual Analysis to Sales Worker."
*   **Sales Worker:** Uses `visual_tools.py` to extract text/embedding -> Searches Pinecone -> Returns "We have this in stock for ₦5,000."

### 3. Instant Feedback
*   **User:** Sends "Hello".
*   **Supervisor:** Immediate Call to Meta API -> **User sees Blue Ticks**.
*   **Planner:** "Assign Greeting to Sales Worker."
*   **Sales Worker:** "Welcome to Ashandy!" (Sent 2s later).

---

## 🐞 Troubleshooting

*   **"Agent is silent":** Check Redis. If the Semantic Cache is locked or the Planner loop exceeds `recursion_limit`, the graph stops.
*   **"No Blue Ticks":** Verify `META_WHATSAPP_TOKEN` has `whatsapp_business_messaging` permission.
*   **"Database Error":** Ensure PostgreSQL is running and `alembic upgrade head` has been run.
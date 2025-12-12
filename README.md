# 🌸 Awéléwà: The AI Sales & Logistics Agent
> **Winner of the Meta AI Developer Academy Hackathon 2025 (Loading...)**

![Status](https://img.shields.io/badge/Status-Active_Development-green)
![Version](https://img.shields.io/badge/Version-1.2-blue)
![Tech](https://img.shields.io/badge/Powered_by-Meta_Llama_4-blueviolet)

**Awéléwà** (Yoruba for *"Beauty has come home"*) is an Agentic AI system designed to solve "Retail Amnesia" for African MSMEs. Unlike passive chatbots, Awéléwà uses **Computer Vision** to "see" products, **Semantic Memory** to build long-term customer relationships, and **Autonomous Logistics** to manage delivery dispatch.

---

## 🎯 Executive Summary

Retail businesses in Nigeria suffer from three core problems:
1.  **Ghost Stock:** Online payments for items that are physically out of stock.
2.  **Retail Amnesia:** Agents forget customer preferences.
3.  **Logistics Chaos:** Manual calculation of delivery fees leads to losses.

**Awéléwà solves this by:**
* **Seeing:** Identifies products from user photos using **Meta SAM + DINOv3**.
* **Remembering:** Recalls user preferences/budget using **Pinecone Vector Memory**.
* **Delivering:** Automatically calculates zone-based delivery fees and dispatches riders via **Twilio**.

---

## 🚀 Key Features

### 👁️ Multimodal Visual Search (Meta SAM + DINOv3)
* **Problem:** The client database has **ZERO** product images.
* **Solution:** Users upload a photo of the product they want.
* **Tech:** **Segment Anything Model (SAM)** extracts the object -> **DINOv3** generates embeddings -> **Pinecone** finds the matching SKU in inventory.
* **Privacy:** Strictly processes **Product Images ONLY**. Faces are ignored to comply with **NDPR**.

### 🧠 Semantic Client Memory (CRM)
* **Tech:** **Pinecone** + **Llama 4 Scout**.
* **Capability:** Remembers context across sessions (e.g., *"Do you want the same oily skin serum as last month?"*).
* **Compliance:** NDPR Transparency Notice included in welcome flow.

### 📦 Intelligent Delivery Logistics (The "Agentic" Workflow)
* **Tech:** **Twilio API** + Geolocation Logic.
* **Role:** The agent calculates delivery fees in real-time based on the distance from the **Store (Origin)**.
* **Pricing Logic (Ibadan Zones):**
    * **Zone A (Shop to Bodhija):** ₦500
    * **Zone B (Bodhija to Alakia):** ₦2,000
    * **Zone C (Outskirts):** ₦3,000
    * **Inter-State:** ₦1,500 (Park Logistics Fee)
* **Dispatch:** Automatically sends an SMS to the rider with the order details when payment is confirmed.

---

## 🏗️ System Architecture

Awéléwà uses **LangGraph** to orchestrate a team of 7 specialized AI Agents:

1.  **🚦 Router Agent:** Classifies input (Text vs. Image vs. Admin Command).
2.  **🛡️ Safety Agent:** Uses **Llama Guard** to filter toxicity and enforce NDPR (blocks face images).
3.  **👁️ Visual Search Agent:** Handles image processing pipeline.
4.  **🧠 Sales Consultant:** Uses **Llama 4 Scout** for product advice and persuasion.
5.  **📦 Delivery Agent:** Calculates fees and manages Twilio dispatch.
6.  **💳 Payment Agent:** Generates Paystack links and listens for webhooks.
7.  **🛠️ Admin Agent:** Handles management commands (`/stock`, `/report`).

---

## 🔧 Technology Stack

* **Backend Framework:** FastAPI (Python 3.11)
* **AI Models:**
    * **Conversational:** Meta Llama 4 Scout (Multimodal)
    * **Vision:** Meta SAM (Segment Anything) + DINOv3
    * **Safety:** Llama Guard 3
* **Database:**
    * **Vector Store:** Pinecone (User Memory + Product Embeddings)
    * **Relational:** PostgreSQL (Orders, Logs, Inventory)
    * **Caching:** Redis (Semantic Cache for speed)
* **Integrations:**
    * **Messaging:** WhatsApp Cloud API
    * **Payments:** Paystack API
    * **Logistics:** Twilio SMS
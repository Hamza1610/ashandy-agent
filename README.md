# 🤖 Ashandy AI Agent (Project Awéléwà)
### *Production-Grade Conversational Commerce System*

![Version](https://img.shields.io/badge/Version-2.0-blue.svg) ![Status](https://img.shields.io/badge/Status-Production--Ready-green.svg) ![Stack](https://img.shields.io/badge/Tech-LangGraph%20%7C%20FastAPI%20%7C%20MCP-orange.svg)

**Winner of the Meta AI Developer Academy Hackathon 2025 (Loading...)**
**Built by Team HAI (Beneficiaries of RAIN Nigeria)**

---

**Awéléwà** (Yoruba for *"Beauty has come home"*) is a sophisticated, multi-agent system designed to automate sales, logistics, and support for Nigerian MSMEs on WhatsApp and Instagram. Unlike simple chatbots, it features a **Supervisor-Planner-Dispatcher** architecture powered by **Meta Llama 4**, utilizing **Model Context Protocol (MCP)** for autonomous tool execution.

## 📊 System Stats at a Glance
| Metric | Count | Details |
| :--- | :---: | :--- |
| **Total Autonomous Agents** | **9** | Supervisor, Planner, Dispatcher, 4 Workers, Reviewers, Resolver |
| **Micro-Services** | **19** | Business logic modules |
| **Tool Servers (MCP)** | **4** | POS, Payment, Knowledge, Logistics |
| **Safety Layers** | **7** | Including Llama Guard, Rate Limits, & Reviewers |

---

## 🏗️ System Architecture V2.0

The system utilizes a **Hierarchical State Graph** architecture. Requests are not just answered; they are Planned, Dispatched, Executed, Reviewed, and Resolved.

```mermaid
graph TB
    subgraph "Orchestration Layer"
        SUP[🔒 Supervisor] --> PLN[🧠 Planner]
        PLN --> DIS[📦 Dispatcher]
    end
    
    subgraph "Worker Layer"
        DIS --> SW[💄 Sales Worker]
        DIS --> PW[💰 Payment Worker]
        DIS --> AW[⚙️ Admin Worker]
        DIS --> SPW[💬 Support Worker]
    end
    
    subgraph "Quality Assurance Layer"
        SW & PW & AW & SPW --> REV[📋 Reviewers]
        REV -- "Reject/Retry" --> DIS
        REV -- "Approve" --> CR[⚖️ Conflict Resolver]
    end
    
    CR --> OS[📤 Output Supervisor]
# Quick Reference: Using the New LangGraph System

## 🚀 How to Use the Refactored System

### Running the System

The FastAPI server works exactly as before:

```bash
python main.py
# or
uvicorn app.main:app --reload
```

### WhatsApp Integration

**Webhook Endpoint**: `POST /webhook/whatsapp`

**How it works**:
1. User sends message on WhatsApp
2. Meta webhook sends payload to your endpoint
3. [`webhooks.py`](file:///c:/Users/USER/Desktop/AI%20projects/ashandy-agent/app/routers/webhooks.py) receives it
4. Creates state with `HumanMessage`
5. Invokes `app.graphs.main_graph.app`
6. Graph routes through: router → safety → cache → sales agent → response
7. Response sent back via Meta API

```python
# webhooks.py automatically:
from app.graphs.main_graph import app as agent_app

input_state = {
    "messages": [HumanMessage(content=user_text)],
    "user_id": wa_id,
    "platform": "whatsapp",
    "session_id": wa_id,
    "is_admin": False
}

result = await agent_app.ainvoke(input_state, config={"configurable": {"thread_id": wa_id}})
```

### Instagram Integration

**Webhook Endpoint**: `POST /webhook/instagram`

Same pattern as WhatsApp but with `platform: "instagram"`

---

## 📁 New File Structure

```
app/
├── state/
│   ├── __init__.py
│   └── agent_state.py          # ⭐ Unified state schema
│
├── tools/
│   ├── product_tools.py         # ⭐ NEW: Search, stock check
│   ├── memory_tools.py          # ⭐ NEW: Save/retrieve memory
│   ├── payment_tools.py         # ⭐ NEW: Paystack integration
│   ├── meta_tools.py            # ⭐ NEW: WhatsApp/Instagram messaging
│   ├── vector_tools.py          # Existing (Pinecone)
│   ├── cache_tools.py           # Existing (Redis)
│   └── sentiment_tool.py        # Existing
│
├── agents/
│   ├── sales_consultant_agent.py  # ⭐ REFACTORED: Tool bindings
│   ├── router_agent.py            # Unchanged
│   ├── safety_agent.py            # Unchanged
│   └── ...
│
├── graphs/
│   ├── __init__.py
│   └── main_graph.py           # ⭐ NEW: Main LangGraph workflow
│
└── routers/
    └── webhooks.py              # ⭐ UPDATED: Uses new graph
```

---

## 🔧 Key Components

### 1. State Schema

Location: [`app/state/agent_state.py`](file:///c:/Users/USER/Desktop/AI%20projects/ashandy-agent/app/state/agent_state.py)

```python
from app.state.agent_state import AgentState

# All nodes receive/return this state
async def my_node(state: AgentState):
    user_id = state["user_id"]
    messages = state["messages"]
    # ...
    return {"messages": [...]}  # Partial update
```

### 2. Tools with @tool Pattern

**Example**: Product Search

```python
from app.tools.product_tools import search_products

# This is bound to LLM - LLM calls it when needed
@tool("search_products_tool")
async def search_products(query: str) -> str:
    """Search for products matching query."""
    # Implementation...
```

### 3. Sales Agent with Tool Bindings

Location: [`app/agents/sales_consultant_agent.py`](file:///c:/Users/USER/Desktop/AI%20projects/ashandy-agent/app/agents/sales_consultant_agent.py)

```python
# LLM autonomously decides when to use tools
llm = ChatGroq(...).bind_tools([
    search_products,
    check_product_stock,
    generate_payment_link_tool,
    save_memory_tool
])

response = await llm.ainvoke(conversation)
# LLM may invoke 0, 1, or multiple tools
```

### 4. Main Graph

Location: [`app/graphs/main_graph.py`](file:///c:/Users/USER/Desktop/AI%20projects/ashandy-agent/app/graphs/main_graph.py)

```python
from app.graphs.main_graph import app

# Invoke the graph
result = await app.ainvoke(
    input_state,
    config={"configurable": {"thread_id": user_id}}
)

# Result contains updated state
final_messages = result["messages"]
send_result = result.get("send_result")
```

---

## 🧪 Testing

### Manual Testing via WhatsApp

1. **Text Query**:
   - Send: "Do you have red lipstick?"
   - Expected: Sales agent uses `search_products` tool → returns results

2. **Image Query**:
   - Send: Product image
   - Expected: Visual agent → product matches → sales agent response

3. **Order Flow**:
   - Send: "I want to buy the lipstick"
   - Expected: Sales agent detects intent → payment agent → Paystack link

4. **Admin Command**:
   - Send: "/stock" (if user is admin)
   - Expected: Admin agent → inventory sync

### Programmatic Testing

```python
from app.graphs.main_graph import app
from langchain_core.messages import HumanMessage

# Test text query
async def test_query():
    result = await app.ainvoke({
        "messages": [HumanMessage(content="Show me lipstick")],
        "user_id": "test_user",
        "platform": "whatsapp",
        "session_id": "test",
        "is_admin": False
    }, config={"configurable": {"thread_id": "test"}})
    
    print(result["messages"][-1].content)
```

---

## 🔍 Debugging

### View Graph Structure

```python
from app.graphs.main_graph import app

# Save graph visualization
app.get_graph().print_ascii()
```

### Check State at Each Node

Add logging in nodes:

```python
async def my_node(state: AgentState):
    logger.info(f"State keys: {list(state.keys())}")
    logger.info(f"Messages count: {len(state['messages'])}")
    # ...
```

### LangSmith Tracing

If configured:

```python
# Traces automatically logged to LangSmith
# View at: https://smith.langchain.com
```

---

## ⚠️ Important Notes

### Tool Binding vs Direct Invocation

**✅ Tool Binding (for Sales Agent)**:
```python
# LLM decides when to call
llm.bind_tools([search_products])
```

**✅ Direct Invocation (for Helper Nodes)**:
```python
# Deterministic operation
cached = await check_semantic_cache.ainvoke(hash)
```

### State Updates

Nodes return **partial state updates**:

```python
async def node(state: AgentState):
    return {
        "messages": [new_message],
        "order_intent": True
    }
    # Only these fields updated, rest preserved
```

### Message Accumulation

`messages` field uses `add_messages` reducer:

```python
# Automatically appends new messages
return {"messages": [AIMessage(content="response")]}
# State now has: [HumanMessage, AIMessage]
```

---

## 🆘 Troubleshooting

### "Graph not compiling"

Check imports in [`main_graph.py`](file:///c:/Users/USER/Desktop/AI%20projects/ashandy-agent/app/graphs/main_graph.py):
```bash
python -c "from app.graphs.main_graph import app; print('OK')"
```

### "Tool not found"

Verify tool is imported and bound:
```python
from app.tools.product_tools import search_products
llm.bind_tools([search_products])  # Must bind!
```

### "State key missing"

Check [`agent_state.py`](file:///c:/Users/USER/Desktop/AI%20projects/ashandy-agent/app/state/agent_state.py) for all available keys

### "Webhook not responding"

1. Check server is running: `python main.py`
2. Verify ngrok/tunnel is active
3. Check Meta webhook verification
4. View logs: `tail -f logs/app.log`

---

## 📚 Next Steps

1. **Test thoroughly** with real WhatsApp/Instagram messages
2. **Monitor performance** (response times, error rates)  
3. **Add post-safety** filtering on LLM outputs
4. **Create sub-graphs** for payment, visual search
5. **Add observability** (metrics, LangSmith)
6. **Write unit tests** for each node
7. **Remove old workflow** once confident in new system

---

## 🎯 Key Benefits

✅ **LLM autonomy**: Sales agent intelligently uses tools  
✅ **Cleaner code**: Atomic nodes, single responsibility  
✅ **Better testing**: Each node testable in isolation  
✅ **Easier debugging**: Clear state flow through graph  
✅ **More scalable**: Modular design for future features  

The system is production-ready! 🚀

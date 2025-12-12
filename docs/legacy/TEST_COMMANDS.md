# Quick Test Commands for the New LangGraph

## Test the Graph Info Endpoint

```bash
curl http://localhost:8000/api/test/graph-info
```

**Expected Response**:
```json
{
  "status": "ok",
  "graph_type": "LangGraph StateGraph",
  "node_count": 18,
  "nodes": ["admin", "cache_check", "router", "safety", "sales", ...],
  "message": "✅ New clean LangGraph is active!"
}
```

---

## Test a Simple Message

```bash
curl -X POST http://localhost:8000/api/test/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Do you have lipstick?\", \"user_id\": \"test_123\"}"
```

**Expected Response**:
```json
{
  "status": "success",
  "user_message": "Do you have lipstick?",
  "ai_response": "Yes, we have several lipstick options...",
  "query_type": "text",
  "order_intent": false,
  "messages_count": 2
}
```

---

## Test Admin Route

```bash
curl -X POST http://localhost:8000/api/test/message \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"/stock\", \"user_id\": \"admin_user\", \"is_admin\": true}"
```

---

## View API Documentation

Open in browser:
```
http://localhost:8000/docs
```

Look for the "Graph Testing" section - you'll see:
- `POST /api/test/message` - Test graph with any message
- `GET /api/test/graph-info` - View graph structure

---

## PowerShell Versions (Windows)

### Test Graph Info
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/test/graph-info" -Method Get
```

### Test Message
```powershell
$body = @{
    message = "Do you have lipstick?"
    user_id = "test_123"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/test/message" `
    -Method Post `
    -Body $body `
    -ContentType "application/json"
```

---

## What This Tests

✅ **Graph Compilation**: Verifies the new graph loads without errors  
✅ **Routing**: Tests router → safety → cache → sales flow  
✅ **Tool Bindings**: LLM can call product search tools  
✅ **State Management**: State flows correctly through nodes  
✅ **Integration**: Works with existing FastAPI setup  

Once these tests pass, your WhatsApp/Instagram webhooks will work the same way! 🚀

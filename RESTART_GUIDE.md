# 🔧 Quick Start After Cache Clear

## Step 1: Start Server
```powershell
uvicorn main:app --reload --env-file .env
```

## Step 2: Test via WhatsApp

Send any message via WhatsApp and check logs for:

```
Router: Processing message...
Router: Extracted string content: 'your message here'
🧠 Retrieving memory for user: +234xxx
```

## Step 3: Check for These Logs

### ✅ Expected (Memory Working):
```
Router: last_user_message='your message'
🧠 Retrieving memory for user: +234xxx  
ℹ️  No previous memory (new customer) OR ✅ Memory found
Sales agent processing for user +234xxx
RESULT FROM AGENT: [response]
Saving interaction memory for +234xxx
```

### ❌ Problem (Still Broken):
```
RESULT FROM AGENT: [response]
Memory skipped. Human: False, AI: True
```

## Step 4: If Still Broken

Check webhook validation - send me the FULL webhook payload that's being sent, including the structure.

The 422 errors suggest payload validation is failing. We may need to add required fields to the webhook input state.

## Quick Test Command

After server starts:
```powershell
$body = '{"message": "test memory", "user_id": "+2349999999999", "platform": "whatsapp"}'
Invoke-RestMethod -Uri http://localhost:8000/api/test/message -Method Post -Body $body -ContentType "application/json"
```

Look for `🧠 Retrieving memory` in logs!

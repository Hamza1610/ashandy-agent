# API Endpoints Documentation

> **Note**: Auto-generated interactive docs available at `/docs` (Swagger UI) and `/redoc`.

---

## 1. Webhooks

### GET /webhook/whatsapp
- **Purpose**: Meta WhatsApp Cloud API verification challenge
- **Params**: `hub.mode`, `hub.verify_token`, `hub.challenge`
- **Response**: Returns `hub.challenge` integer on success

### POST /webhook/whatsapp
- **Purpose**: Receive incoming WhatsApp messages
- **Rate Limit**: 60/minute per IP
- **Body**: Meta Webhook Payload (WhatsAppWebhookPayload)
- **Flow**: Routes to LangGraph agent pipeline

### GET /webhook/instagram
- **Purpose**: Meta Instagram verification challenge
- **Params**: Same as WhatsApp

### POST /webhook/instagram
- **Purpose**: Receive Instagram DMs and story replies
- **Body**: InstagramWebhookPayload
- **Features**: Extracts story/post context for product inquiries

### POST /webhook/paystack
- **Purpose**: Payment success/failure events
- **Headers**: `x-paystack-signature` (HMAC SHA512 verification)
- **Body**: Paystack event object
- **Flow**: Notifies manager on successful payment

---

## 2. Health & Monitoring

### GET /health
- **Purpose**: Basic service health check
- **Response**: `{"status": "healthy"}`

### GET /health/mcp
- **Purpose**: MCP server connection status
- **Response**: `{"pos": "connected", "knowledge": "connected", ...}`

### GET /health/keys
- **Purpose**: API key rotation status
- **Response**: `{"groq": "valid", "together": "valid", ...}`

---

## 3. Testing (Development Only)

### POST /api/test/message
- **Purpose**: Test agent without WhatsApp
- **Body**: `{"user_id": "test", "message": "Hello"}`
- **Response**: Agent response

---

## 4. Admin (If Enabled)

### GET /admin/reports/weekly
- **Purpose**: Generate weekly performance report
- **Auth**: Admin phone number required

### POST /admin/broadcast
- **Purpose**: Send message to customer list
- **Body**: `{"message": "...", "user_ids": [...]}`

---

## Authentication

| Endpoint | Auth Method |
|----------|-------------|
| Webhooks | Signature verification (Meta/Paystack) |
| Health | None (public) |
| Admin | Phone number whitelist |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/webhook/whatsapp` | 60/min |
| `/webhook/instagram` | 60/min |
| Others | No limit |

---

## Error Responses

```json
{
  "status": "error",
  "message": "Description of error"
}
```

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid payload) |
| 401 | Unauthorized (invalid signature) |
| 403 | Forbidden (verification failed) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

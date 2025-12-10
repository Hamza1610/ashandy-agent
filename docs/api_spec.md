# API Endpoints Documentation

## 1. Webhooks

### GET /webhook/whatsapp
- **Purpose**: Verification challenge for Meta WhatsApp Cloud API.
- **Params**: `hub.mode`, `hub.verify_token`, `hub.challenge`.
- **Response**: Returns `hub.challenge` integer.

### POST /webhook/whatsapp
- **Purpose**: Receive WhatsApp messages.
- **Body**: Standard Meta Webhook Payload.
- **Logic**: Routes to LangGraph agent workflow.

### POST /webhook/paystack
- **Purpose**: Receive payment success events.
- **Headers**: `x-paystack-signature` for verification.
- **Body**: Paystack event object.

## 2. System

### GET /health
- **Purpose**: Service health check.
- **Response**: `{"status": "healthy"}`

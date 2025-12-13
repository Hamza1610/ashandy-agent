"""
Paystack Webhook Handler for Payment Verification
Receives payment confirmation from Paystack and triggers delivery flow
"""
from fastapi import APIRouter, Request, HTTPException, Header
from app.services.paystack_service import paystack_service
from app.services.order_service import update_order_status, get_order_by_reference  # NEW
from app.agents.delivery_agent import delivery_agent_node
from app.state.agent_state import AgentState
from app.utils.order_parser import format_items_summary  # NEW
from datetime import datetime
import logging
import hmac
import hashlib

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/paystack/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None)
):
    """
    Handle Paystack payment webhook events.
    
    Triggered when:
    - Payment is successful
    - Payment fails
    - Charge is successful
    
    On success: Triggers delivery agent to send SMS
    """
    print(f"\n{'='*100}")
    print(f">>> PAYSTACK WEBHOOK RECEIVED")
    print(f"{'='*100}\n")
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Verify webhook signature
        from app.utils.config import settings
        secret = settings.PAYSTACK_WEBHOOK_SECRET
        
        if secret and x_paystack_signature:
            # Calculate HMAC
            calculated_signature = hmac.new(
                secret.encode('utf-8'),
                body_str.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
            
            if calculated_signature != x_paystack_signature:
                logger.warning("Invalid Paystack webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")
            
            print(f">>> WEBHOOK: Signature verified ✓")
        
        # Parse JSON payload
        import json
        payload = json.loads(body_str)
        
        event = payload.get('event')
        data = payload.get('data', {})
        
        print(f">>> WEBHOOK: Event type = {event}")
        print(f">>> WEBHOOK: Reference = {data.get('reference')}")
        print(f">>> WEBHOOK: Status = {data.get('status')}")
        print(f">>> WEBHOOK: Amount = ₦{data.get('amount', 0) / 100:,.2f}")
        
        # Only process successful charges
        if event == 'charge.success' and data.get('status') == 'success':
            reference = data.get('reference')
            amount = data.get('amount', 0) / 100  # Convert from kobo
            customer_email = data.get('customer', {}).get('email')
            
            print(f"\n>>> WEBHOOK: ✓ Payment successful!")
            print(f">>>   Reference: {reference}")
            print(f">>>   Amount: ₦{amount:,.2f}")
            print(f">>>   Email: {customer_email}")
            
            # Step 1: Update order status in database
            print(f"\n>>> WEBHOOK: Updating order status to 'paid'...")
            try:
                order = await update_order_status(
                    reference=reference,
                    payment_status='paid',
                    paid_at=datetime.utcnow()
                )
                
                if not order:
                    logger.warning(f"Order not found for reference: {reference}")
                    print(f">>> WEBHOOK WARNING: Order not found in database")
                    # Create minimal delivery state if order not in DB
                    delivery_state = {
                        "order_data": {
                            "order_id": reference,
                            "customer_email": customer_email,
                            "customer_name": "Customer",
                            "customer_phone": "Unknown",
                            "items_summary": "Order items",
                            "total_amount": f"₦{amount:,.0f}",
                            "pickup_location": "Ashandy Store, Ibadan",
                            "delivery_address": "To be confirmed",
                            "rider_phone": None,
                            "manager_phone": None
                        }
                    }
                else:
                    print(f">>> WEBHOOK: ✓ Order updated (ID: {order.order_id})")
                    
                    # Step 2: Prepare delivery state with full order details from DB
                    delivery_state = {
                        "order_data": {
                            "order_id": reference,
                            "db_order_id": str(order.order_id),
                            "customer_email": order.customer_email,
                            "customer_name": order.customer_name,
                            "customer_phone": order.customer_phone,
                            "items": order.items,
                            "items_summary": format_items_summary(order.items),
                            "total_amount": f"₦{order.total_amount:,.0f}",
                            "pickup_location": order.pickup_location,
                            "delivery_address": order.delivery_address,
                            "rider_phone": order.rider_phone,
                            "manager_phone": None
                        }
                    }
                    
            except Exception as e:
                logger.error(f"Order update failed: {e}", exc_info=True)
                print(f">>> WEBHOOK ERROR: Order update failed - {e}")
                # Create minimal state as fallback
                delivery_state = {
                    "order_data": {
                        "order_id": reference,
                        "customer_email": customer_email,
                        "customer_name": "Customer",
                        "customer_phone": "Unknown",
                        "items_summary": "Order items",
                        "total_amount": f"₦{amount:,.0f}",
                        "pickup_location": "Ashandy Store, Ibadan",
                        "delivery_address": "To be confirmed",
                        "rider_phone": None,
                        "manager_phone": None
                    }
                }
            
            print(f"\n>>> WEBHOOK: Triggering delivery agent...")
            
            try:
                # Call delivery agent
                result = await delivery_agent_node(delivery_state)
                
                print(f">>> WEBHOOK: Delivery agent completed")
                print(f">>>   Rider status: {result.get('rider_notification_status')}")
                print(f">>>   Manager status: {result.get('manager_notification_status')}")
                
                logger.info(f"Payment verified and delivery triggered: {reference}")
                
            except Exception as e:
                logger.error(f"Delivery agent error: {e}", exc_info=True)
                print(f">>> WEBHOOK ERROR: Delivery failed - {e}")
            
            return {
                "status": "success",
                "message": "Payment verified and delivery triggered",
                "reference": reference
            }
        
        else:
            print(f">>> WEBHOOK: Event ignored (not success)")
            return {
                "status": "ignored",
                "message": f"Event {event} not processed"
            }
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        print(f">>> WEBHOOK ERROR: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paystack/test")
async def test_paystack_webhook():
    """
    Test endpoint to verify webhook is accessible.
    """
    return {
        "status": "ok",
        "message": "Paystack webhook endpoint is active",
        "endpoint": "/webhook/paystack/webhook"
    }

"""
Manual Payment Verification Tools: Admin tools for verifying bank transfer payments.
"""
from langchain_core.tools import tool
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.services.meta_service import meta_service
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@tool
async def get_pending_manual_payments(limit: int = 10) -> str:
    """Get list of customers awaiting manual payment verification.
    
    Shows customers who were given manual payment instructions but haven't
    been confirmed yet. Manager should review payment proof and confirm.
    
    Args:
        limit: Maximum number of pending payments to show (default: 10)
        
    Returns:
        Formatted list of pending manual payments with details
    """
    try:
        async with AsyncSessionLocal() as session:
            # Query for orders with manual_payment_pending status
            query = text("""
                SELECT 
                    user_id,
                    amount,
                    reference,
                    created_at,
                    delivery_details
                FROM orders
                WHERE payment_status = 'manual_payment_pending'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"limit": limit})
            rows = result.fetchall()
            
            if not rows:
                return "✅ No pending manual payments to review."
            
            output = f"💳 **Pending Manual Payments ({len(rows)})**\\n\\n"
            output += "Review payment proof on WhatsApp and use `confirm_manual_payment` or `reject_manual_payment`\\n\\n"
            
            for row in rows:
                r = dict(row._mapping)
                user_id = r.get('user_id', 'Unknown')
                masked_id = f"...{user_id[-10:]}" if len(user_id) > 10 else user_id
                amount = r.get('amount', 0)
                reference = r.get('reference', 'N/A')
                created = r.get('created_at', 'N/A')
                
                output += f"""---
**Customer:** {masked_id}
**Amount:** ₦{amount:,.2f}
**Reference:** {reference}
**Requested:** {created}
**Action:** Check WhatsApp for payment proof from {masked_id}

"""
            
            return output
            
    except Exception as e:
        logger.error(f"Error getting pending payments: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@tool
async def confirm_manual_payment(
    customer_id: str,
    amount: float,
    reference: str,
    notes: str = "Payment verified via bank transfer"
) -> str:
    """Confirm that customer's manual bank transfer payment has been received.
    
    Manager should:
    1. Check WhatsApp for payment proof screenshot
    2. Verify amount matches bank statement
    3. Call this tool to confirm
    
    This will:
    - Update order status to 'paid'
    - Send confirmation WhatsApp message to customer
    - Proceed order to fulfillment
    
    Args:
        customer_id: Customer's phone number (e.g., +2348012345678)
        amount: Amount confirmed in bank (must match order total)
        reference: Payment reference from order
        notes: Optional notes about verification (default: "Payment verified")
        
    Returns:
        Confirmation status and customer notification result
    """
    try:
        logger.info(f"💳 Confirming manual payment: {customer_id}, ₦{amount}, ref={reference}")
        
        async with AsyncSessionLocal() as session:
            # Update order status
            update_query = text("""
                UPDATE orders 
                SET payment_status = 'paid',
                    verified_at = NOW(),
                    verification_notes = :notes
                WHERE user_id = :user_id 
                  AND reference = :reference
                  AND payment_status = 'manual_payment_pending'
                RETURNING id, amount
            """)
            result = await session.execute(update_query, {
                "user_id": customer_id,
                "reference": reference,
                "notes": notes
            })
            await session.commit()
            
            updated_order = result.fetchone()
            if not updated_order:
                return f"❌ No pending payment found for {customer_id} with reference {reference}"
            
            order_id = updated_order[0]
            order_amount = updated_order[1]
            
            # Verify amount matches
            if abs(order_amount - amount) > 0.01:  # Allow 1 kobo tolerance for float precision
                logger.warning(f"Amount mismatch: Order=₦{order_amount}, Confirmed=₦{amount}")
                # Rollback
                await session.rollback()
                return f"⚠️ Amount mismatch! Order total: ₦{order_amount:,.2f}, but you're confirming ₦{amount:,.2f}. Please verify."
            
            # Send confirmation to customer
            confirmation_message = f"""✅ *Payment Confirmed!*

Your payment of ₦{amount:,.2f} has been received and verified.

📦 Your order is now being processed for delivery.
Reference: {reference}

Thank you for your patience! 💕"""
            
            try:
                send_result = await meta_service.send_whatsapp_message(
                    recipient_id=customer_id,
                    message_text=confirmation_message
                )
                
                if send_result:
                    notification_status = "✅ Customer notified via WhatsApp"
                else:
                    notification_status = "⚠️ Payment confirmed but WhatsApp notification failed"
            except Exception as e:
                logger.error(f"Error sending confirmation: {e}")
                notification_status = f"⚠️ Payment confirmed but notification error: {str(e)}"
            
            return f"""✅ **Manual Payment Confirmed**

**Order ID:** {order_id}
**Customer:** {customer_id}
**Amount:** ₦{amount:,.2f}
**Reference:** {reference}

{notification_status}

Order status updated to: PAID → Proceed to fulfillment"""
            
    except Exception as e:
        logger.error(f"Error confirming payment: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@tool
async def reject_manual_payment(
    customer_id: str,
    reference: str,
    reason: str
) -> str:
    """Reject a manual payment (e.g., wrong amount, fake screenshot).
    
    Manager should use this when:
    - Payment proof is invalid/fake
    - Amount doesn't match order
    - No payment received in bank
    
    This will:
    - Mark payment as rejected
    - Send rejection message to customer with reason
    - Ask customer to provide correct payment or contact support
    
    Args:
        customer_id: Customer's phone number
        reference: Payment reference from order
        reason: Why payment was rejected (will be shown to customer)
        
    Returns:
        Rejection status and customer notification result
    """
    try:
        logger.info(f"❌ Rejecting manual payment: {customer_id}, ref={reference}, reason={reason}")
        
        async with AsyncSessionLocal() as session:
            # Update order status
            update_query = text("""
                UPDATE orders 
                SET payment_status = 'payment_rejected',
                    verified_at = NOW(),
                    verification_notes = :reason
                WHERE user_id = :user_id 
                  AND reference = :reference
                  AND payment_status = 'manual_payment_pending'
                RETURNING id, amount
            """)
            result = await session.execute(update_query, {
                "user_id": customer_id,
                "reference": reference,
                "reason": f"REJECTED: {reason}"
            })
            await session.commit()
            
            rejected_order = result.fetchone()
            if not rejected_order:
                return f"❌ No pending payment found for {customer_id} with reference {reference}"
            
            order_id = rejected_order[0]
            order_amount = rejected_order[1]
            
            # Send rejection message to customer
            rejection_message = f"""⚠️ *Payment Verification Issue*

We could not verify your payment for reference: {reference}

**Reason:** {reason}

**Expected Amount:** ₦{order_amount:,.2f}

Please:
1. Check you transferred the correct amount
2. Verify you sent proof to the right WhatsApp number
3. Contact support for assistance

We're here to help! 💙"""
            
            try:
                send_result = await meta_service.send_whatsapp_message(
                    recipient_id=customer_id,
                    message_text=rejection_message
                )
                
                if send_result:
                    notification_status = "✅ Customer notified via WhatsApp"
                else:
                    notification_status = "⚠️ Payment rejected but WhatsApp notification failed"
            except Exception as e:
                logger.error(f"Error sending rejection: {e}")
                notification_status = f"⚠️ Payment rejected but notification error: {str(e)}"
            
            return f"""❌ **Manual Payment Rejected**

**Order ID:** {order_id}
**Customer:** {customer_id}
**Reference:** {reference}
**Reason:** {reason}

{notification_status}

Order status: PAYMENT_REJECTED → Customer needs to resubmit or contact support"""
            
    except Exception as e:
        logger.error(f"Error rejecting payment: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"

"""
SMS Test Router: Test Twilio SMS functionality
Helps debug SMS delivery issues without going through full payment flow
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.tools.sms_tools import send_rider_sms, notify_manager
from app.utils.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class SMSTestRequest(BaseModel):
    phone: str = "+2349026880099"  # Default test number
    message_type: str = "rider"  # 'rider' or 'manager'


@router.post("/test/sms")
async def test_sms(request: SMSTestRequest):
    """
    Test SMS delivery via Twilio.
    
    Request body:
    {
        "phone": "+2349026880099",
        "message_type": "rider"  // or "manager"
    }
    
    This helps diagnose Twilio connectivity issues.
    """
    print(f"\n{'='*80}")
    print(f">>> SMS TEST ENDPOINT CALLED")
    print(f">>> Phone: {request.phone}")
    print(f">>> Type: {request.message_type}")
    print(f"{'='*80}\n")
    
    try:
        # Test data
        test_order_id = "TEST-ORDER-123"
        test_customer_phone = "+2349026880099"
        
        if request.message_type == "rider":
            print(f">>> Testing RIDER SMS...")
            
            result = await send_rider_sms.ainvoke({
                "rider_phone": request.phone,
                "pickup_location": "Ashandy Store, Ibadan",
                "delivery_address": "Test Address, 123 Test St, Lagos",
                "order_id": test_order_id,
                "customer_phone": test_customer_phone
            })
            
            print(f">>> Rider SMS Result: {result}")
            
            return {
                "status": "success" if "successfully" in result.lower() else "failed",
                "message": result,
                "phone": request.phone,
                "type": "rider"
            }
        
        elif request.message_type == "manager":
            print(f">>> Testing MANAGER SMS...")
            
            result = await notify_manager.ainvoke({
                "order_id": test_order_id,
                "customer_name": "Test Customer",
                "items_summary": "1x Test Product (₦5,000 each)",
                "total_amount": "₦6,500",
                "delivery_address": "Test Address, 123 Test St, Lagos",
                "manager_phone": request.phone
            })
            
            print(f">>> Manager SMS Result: {result}")
            
            return {
                "status": "success" if "successfully" in result.lower() else "failed",
                "message": result,
                "phone": request.phone,
                "type": "manager"
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail="message_type must be 'rider' or 'manager'"
            )
    
    except Exception as e:
        logger.error(f"SMS test error: {e}", exc_info=True)
        print(f">>> SMS TEST ERROR: {type(e).__name__}: {str(e)}")
        
        return {
            "status": "error",
            "message": str(e),
            "phone": request.phone,
            "type": request.message_type,
            "error_type": type(e).__name__
        }


@router.get("/test/sms/config")
async def test_sms_config():
    """
    Check Twilio configuration (without exposing secrets).
    """
    from app.utils.config import settings
    
    has_account_sid = bool(settings.TWILIO_ACCOUNT_SID)
    has_auth_token = bool(settings.TWILIO_AUTH_TOKEN)
    has_phone = bool(settings.TWILIO_PHONE_NUMBER)
    
    test_rider = settings.TEST_RIDER_PHONE
    test_manager = settings.TEST_MANAGER_PHONE
    
    return {
        "twilio_configured": has_account_sid and has_auth_token and has_phone,
        "account_sid_set": has_account_sid,
        "auth_token_set": has_auth_token,
        "phone_number_set": has_phone,
        "test_rider_phone": test_rider,
        "test_manager_phone": test_manager,
        "hint": "Use POST /api/test/sms to send test SMS"
    }

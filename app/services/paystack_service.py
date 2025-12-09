from paystackapi.paystack import Paystack
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

class PaystackService:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        if self.secret_key:
            self.paystack = Paystack(secret_key=self.secret_key)
        else:
            logger.warning("PAYSTACK_SECRET_KEY not set. Paystack service initialized in mock mode.")
            self.paystack = None

    def initialize_transaction(self, email: str, amount: int, reference: str):
        """
        Initialize a payment transaction.
        Amount is in kobo (e.g., 500000 = 5000.00 NGN)
        """
        if not self.paystack:
            logger.info(f"Mocking payment initialization for {email}, amount: {amount}")
            return {
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "authorization_url": f"https://checkout.paystack.com/mock-{reference}",
                    "access_code": f"mock-{reference}",
                    "reference": reference
                }
            }

        try:
            response = self.paystack.transaction.initialize(
                email=email,
                amount=amount,
                reference=reference,
                callback_url=f"{settings.CORS_ORIGINS[0]}/payment/callback" # Example
            )
            return response
        except Exception as e:
            logger.error(f"Paystack initialization error: {e}")
            return {"status": False, "message": str(e)}

    def verify_transaction(self, reference: str):
        if not self.paystack:
             logger.info(f"Mocking payment verification for {reference}")
             return {
                 "status": True, 
                 "data": {"status": "success", "reference": reference, "amount": 500000}
             }

        try:
            response = self.paystack.transaction.verify(reference=reference)
            return response
        except Exception as e:
            logger.error(f"Paystack verification error: {e}")
            return {"status": False, "message": str(e)}

paystack_service = PaystackService()

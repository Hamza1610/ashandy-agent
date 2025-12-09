from paystackapi.paystack import Paystack
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

class PaystackService:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        if not self.secret_key:
             # In production, we should probably raise error, or log critical.
             # User requested NO MOCKS.
             logger.critical("PAYSTACK_SECRET_KEY is missing! Service will fail.")
             raise ValueError("PAYSTACK_SECRET_KEY is required for production.")
        
        self.paystack = Paystack(secret_key=self.secret_key)

    def initialize_transaction(self, email: str, amount: int, reference: str):
        """
        Initialize a payment transaction.
        Amount is in kobo (e.g., 500000 = 5000.00 NGN)
        """
        if not self.paystack:
             return {"status": False, "message": "Paystack not initialized"}

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
             return {"status": False, "message": "Paystack not initialized"}

        try:
            response = self.paystack.transaction.verify(reference=reference)
            return response
        except Exception as e:
            logger.error(f"Paystack verification error: {e}")
            return {"status": False, "message": str(e)}

paystack_service = PaystackService()

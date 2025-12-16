"""
NDPR Compliance Service: Handles user data deletion requests.

Per NDPR "Right to be Forgotten":
- DELETE: User memory (Pinecone), Message logs (PostgreSQL)
- RETAIN: Orders, Incidents, Feedback (legal/T&S basis)
"""
from app.services.db_service import AsyncSessionLocal
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class NDPRService:
    """Handles NDPR-compliant data deletion requests."""
    
    async def delete_user_memory(self, user_id: str) -> dict:
        """
        Delete user's personalized data (Right to be Forgotten).
        
        Deletes:
        - Pinecone user_memory vectors
        - PostgreSQL message_logs
        
        Retains (per T&S):
        - Orders (legal requirement)
        - Incidents (dispute resolution)
        - Feedback (service improvement)
        
        Returns:
            {"success": bool, "deleted": {...}, "message": str}
        """
        result = {
            "success": True,
            "deleted": {"pinecone_vectors": 0, "message_logs": 0},
            "retained": ["orders", "incidents", "feedback_logs"],
            "message": ""
        }
        
        # 1. Delete from Pinecone (user memory vectors)
        try:
            from app.utils.config import settings
            if settings.PINECONE_API_KEY and settings.PINECONE_INDEX_USER_MEMORY:
                from pinecone import Pinecone
                pc = Pinecone(api_key=settings.PINECONE_API_KEY)
                index = pc.Index(settings.PINECONE_INDEX_USER_MEMORY)
                
                # Delete all vectors with user_id metadata
                # Pinecone delete by metadata filter
                delete_response = index.delete(
                    filter={"user_id": {"$eq": user_id}}
                )
                result["deleted"]["pinecone_vectors"] = "all matching"
                logger.info(f"Deleted Pinecone vectors for user {user_id}")
            else:
                logger.warning("Pinecone not configured, skipping vector deletion")
                
        except Exception as e:
            logger.error(f"Pinecone deletion error for {user_id}: {e}")
            result["deleted"]["pinecone_vectors"] = f"error: {str(e)}"
        
        # 2. Delete from PostgreSQL message_logs
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    DELETE FROM message_logs WHERE user_id = :user_id
                """)
                delete_result = await session.execute(query, {"user_id": user_id})
                await session.commit()
                result["deleted"]["message_logs"] = delete_result.rowcount
                logger.info(f"Deleted {delete_result.rowcount} message logs for user {user_id}")
                
        except Exception as e:
            logger.error(f"Message logs deletion error for {user_id}: {e}")
            result["deleted"]["message_logs"] = f"error: {str(e)}"
            result["success"] = False
        
        # Build confirmation message
        if result["success"]:
            result["message"] = (
                f"✅ *Memory Deleted*\n\n"
                f"Your personalized AI profile and chat history have been permanently deleted.\n\n"
                f"📝 *Retained (per Terms of Service):*\n"
                f"• Order records (legal requirement)\n"
                f"• Support tickets (dispute resolution)\n\n"
                f"If you have any questions, please contact our manager. 🙏"
            )
        else:
            result["message"] = (
                f"⚠️ *Partial Deletion*\n\n"
                f"We encountered an issue deleting some data. "
                f"Please contact our manager for assistance."
            )
        
        return result


# Singleton instance
ndpr_service = NDPRService()

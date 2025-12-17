"""
Logging Service: Persists all messages to PostgreSQL for historical analysis.
"""
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LoggingService:
    """Service for logging all agent-user interactions to the database."""
    
    async def log_message(
        self,
        user_id: str,
        role: str,  # 'user' | 'assistant' | 'system'
        content: str,
        sentiment_score: float = 0.0,
        intent: str = None,
        platform: str = "whatsapp"
    ) -> bool:
        """
        Log a message to the message_logs table.
        
        Args:
            user_id: WhatsApp number or platform ID
            role: Who sent the message
            content: Message text
            sentiment_score: -1.0 to 1.0
            intent: Detected intent category
            platform: 'whatsapp' or 'instagram'
        
        Returns:
            True if logged successfully
        """
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    INSERT INTO message_logs (user_id, role, content, sentiment_score, intent, platform)
                    VALUES (:user_id, :role, :content, :sentiment_score, :intent, :platform)
                """)
                await session.execute(query, {
                    "user_id": user_id,
                    "role": role,
                    "content": content[:5000],  # Truncate very long messages
                    "sentiment_score": sentiment_score,
                    "intent": intent,
                    "platform": platform
                })
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
            return False
    
    async def get_messages_for_period(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: str = None
    ) -> list:
        """
        Retrieve messages for a date range, optionally filtered by user.
        
        Used for report generation.
        """
        try:
            async with AsyncSessionLocal() as session:
                if user_id:
                    query = text("""
                        SELECT user_id, role, content, sentiment_score, intent, created_at
                        FROM message_logs
                        WHERE created_at BETWEEN :start_date AND :end_date
                        AND user_id = :user_id
                        ORDER BY created_at ASC
                    """)
                    result = await session.execute(query, {
                        "start_date": start_date,
                        "end_date": end_date,
                        "user_id": user_id
                    })
                else:
                    query = text("""
                        SELECT user_id, role, content, sentiment_score, intent, created_at
                        FROM message_logs
                        WHERE created_at BETWEEN :start_date AND :end_date
                        ORDER BY created_at ASC
                    """)
                    result = await session.execute(query, {
                        "start_date": start_date,
                        "end_date": end_date
                    })
                
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    async def get_unique_users_for_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list:
        """Get list of unique user_ids who interacted in a period."""
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT DISTINCT user_id
                    FROM message_logs
                    WHERE created_at BETWEEN :start_date AND :end_date
                    AND role = 'user'
                """)
                result = await session.execute(query, {
                    "start_date": start_date,
                    "end_date": end_date
                })
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get unique users: {e}")
            return []


# Singleton instance
logging_service = LoggingService()

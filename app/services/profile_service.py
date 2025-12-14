"""
Profile Service: Manages customer profiles with retention scoring.
"""
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ProfileService:
    """Service for managing customer profiles and calculating retention scores."""
    
    async def get_or_create_profile(self, user_id: str) -> dict:
        """Get existing profile or create a new one."""
        try:
            async with AsyncSessionLocal() as session:
                query = text("SELECT * FROM customer_profiles WHERE user_id = :user_id")
                result = await session.execute(query, {"user_id": user_id})
                row = result.fetchone()
                
                if row:
                    return dict(row._mapping)
                
                # Create new profile
                insert_query = text("""
                    INSERT INTO customer_profiles (user_id, last_interaction)
                    VALUES (:user_id, NOW())
                    RETURNING *
                """)
                result = await session.execute(insert_query, {"user_id": user_id})
                await session.commit()
                row = result.fetchone()
                return dict(row._mapping) if row else {}
                
        except Exception as e:
            logger.error(f"Failed to get/create profile: {e}")
            return {}
    
    async def update_on_message(
        self,
        user_id: str,
        sentiment_score: float = 0.0
    ):
        """Update profile when user sends a message."""
        try:
            async with AsyncSessionLocal() as session:
                # Upsert: Update if exists, insert if not
                query = text("""
                    INSERT INTO customer_profiles (user_id, message_count, avg_sentiment, last_interaction)
                    VALUES (:user_id, 1, :sentiment, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        message_count = customer_profiles.message_count + 1,
                        avg_sentiment = (customer_profiles.avg_sentiment * customer_profiles.message_count + :sentiment) 
                                        / (customer_profiles.message_count + 1),
                        last_interaction = NOW(),
                        updated_at = NOW()
                """)
                await session.execute(query, {
                    "user_id": user_id,
                    "sentiment": sentiment_score
                })
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to update profile on message: {e}")
    
    async def update_on_purchase(
        self,
        user_id: str,
        amount: float,
        category: str = None
    ):
        """Update profile when user makes a purchase."""
        try:
            async with AsyncSessionLocal() as session:
                # First, get current preferred_categories
                get_query = text("""
                    SELECT preferred_categories FROM customer_profiles WHERE user_id = :user_id
                """)
                result = await session.execute(get_query, {"user_id": user_id})
                row = result.fetchone()
                
                categories = {}
                if row and row[0]:
                    categories = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                
                if category:
                    categories[category] = categories.get(category, 0) + 1
                
                # Update profile
                query = text("""
                    INSERT INTO customer_profiles (user_id, total_purchases, order_count, preferred_categories, last_interaction)
                    VALUES (:user_id, :amount, 1, :categories, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        total_purchases = customer_profiles.total_purchases + :amount,
                        order_count = customer_profiles.order_count + 1,
                        preferred_categories = :categories,
                        last_interaction = NOW(),
                        updated_at = NOW()
                """)
                await session.execute(query, {
                    "user_id": user_id,
                    "amount": amount,
                    "categories": json.dumps(categories)
                })
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to update profile on purchase: {e}")
    
    async def calculate_retention_score(self, user_id: str) -> float:
        """
        Calculate retention score using RFM (Recency, Frequency, Monetary) model.
        
        Returns: Score from 0.0 (likely to churn) to 1.0 (highly retained)
        """
        try:
            profile = await self.get_or_create_profile(user_id)
            if not profile:
                return 0.5  # Default neutral
            
            # Recency Score (days since last interaction)
            last_interaction = profile.get('last_interaction')
            if last_interaction:
                days_ago = (datetime.now(last_interaction.tzinfo) - last_interaction).days
                recency_score = max(0, 1 - (days_ago / 30))  # Decay over 30 days
            else:
                recency_score = 0.5
            
            # Frequency Score (message count, normalized)
            message_count = profile.get('message_count', 0)
            frequency_score = min(1.0, message_count / 20)  # Cap at 20 messages
            
            # Sentiment Score (already -1 to 1, normalize to 0-1)
            avg_sentiment = profile.get('avg_sentiment', 0.0)
            sentiment_normalized = (avg_sentiment + 1) / 2  # Convert to 0-1
            
            # Monetary Score (purchase value, normalized)
            total_purchases = profile.get('total_purchases', 0.0)
            monetary_score = min(1.0, total_purchases / 100000)  # Cap at 100k
            
            # Weighted RFM Score
            retention = (
                0.3 * recency_score +
                0.2 * frequency_score +
                0.2 * sentiment_normalized +
                0.3 * monetary_score
            )
            
            # Update the profile with the new retention score
            async with AsyncSessionLocal() as session:
                query = text("""
                    UPDATE customer_profiles SET retention_score = :score, updated_at = NOW()
                    WHERE user_id = :user_id
                """)
                await session.execute(query, {"user_id": user_id, "score": retention})
                await session.commit()
            
            return round(retention, 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate retention: {e}")
            return 0.5
    
    async def get_all_profiles_for_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list:
        """Get all customer profiles that were active in a period."""
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT * FROM customer_profiles
                    WHERE last_interaction BETWEEN :start_date AND :end_date
                    ORDER BY total_purchases DESC
                """)
                result = await session.execute(query, {
                    "start_date": start_date,
                    "end_date": end_date
                })
                return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get profiles for period: {e}")
            return []


# Singleton instance
profile_service = ProfileService()

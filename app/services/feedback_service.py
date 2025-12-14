"""
Feedback Service: Detects user reactions, logs feedback, aggregates learning.
Includes security protections against malicious manipulation.
"""
from app.services.db_service import AsyncSessionLocal
from app.services.cache_service import cache_service
from sqlalchemy import text
from datetime import datetime, timedelta
import logging
import json
import re

logger = logging.getLogger(__name__)


class FeedbackService:
    """Detects feedback signals from user messages and enables learning."""
    
    # === SECURITY SETTINGS ===
    MAX_FEEDBACK_PER_USER_PER_DAY = 5     # Rate limiting
    MIN_UNIQUE_USERS_FOR_UPDATE = 3       # Minimum users before updating preferences
    ANOMALY_THRESHOLD = 0.90              # Flag users with >90% same feedback type
    TRUSTED_USER_WEIGHT = 2.0             # Multiplier for verified purchasers
    
    # High-confidence positive signals
    POSITIVE_SIGNALS_HIGH = {
        "perfect", "exactly", "that's it", "wonderful", "amazing",
        "excellent", "brilliant", "you're the best", "love it"
    }
    
    # Medium-confidence positive signals
    POSITIVE_SIGNALS_MED = {
        "thanks", "thank you", "great", "good", "nice", "appreciate",
        "helpful", "cool", "awesome", "yes please", "correct"
    }
    
    # Negative signals
    NEGATIVE_SIGNALS_HIGH = {
        "wrong", "not what i asked", "no that's wrong", "incorrect",
        "you don't understand", "that's not it", "useless", "terrible"
    }
    
    NEGATIVE_SIGNALS_MED = {
        "no", "nope", "not really", "hmm", "confused", "what?",
        "i said", "again", "repeat", "didn't ask for"
    }
    
    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded daily feedback limit. Returns True if allowed."""
        cache_key = f"feedback_limit:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = await cache_service.get(cache_key)
            if count and int(count) >= self.MAX_FEEDBACK_PER_USER_PER_DAY:
                logger.warning(f"Feedback rate limit exceeded for {user_id}")
                return False
            
            new_count = (int(count) + 1) if count else 1
            await cache_service.set(cache_key, str(new_count), expire=86400)
            return True
        except Exception as e:
            logger.warning(f"Rate limit check failed, allowing: {e}")
            return True
    
    async def detect_and_log_feedback(
        self,
        user_id: str,
        message: str,
        previous_ai_response: str = None,
        context_topic: str = None,
        session_id: str = None
    ) -> dict | None:
        """Detect feedback signals in user message and log to database."""
        message_lower = message.lower().strip()
        
        if len(message_lower) < 2:
            return None
        
        feedback_type = None
        signal_strength = None
        matched_signal = None
        
        # Check positive signals
        for signal in self.POSITIVE_SIGNALS_HIGH:
            if signal in message_lower:
                feedback_type = "positive"
                signal_strength = "high"
                matched_signal = signal
                break
        
        if not feedback_type:
            for signal in self.POSITIVE_SIGNALS_MED:
                if signal in message_lower:
                    feedback_type = "positive"
                    signal_strength = "medium"
                    matched_signal = signal
                    break
        
        if not feedback_type:
            for signal in self.NEGATIVE_SIGNALS_HIGH:
                if signal in message_lower:
                    feedback_type = "negative"
                    signal_strength = "high"
                    matched_signal = signal
                    break
        
        if not feedback_type:
            for signal in self.NEGATIVE_SIGNALS_MED:
                if re.search(rf'\b{re.escape(signal)}\b', message_lower):
                    feedback_type = "negative"
                    signal_strength = "medium"
                    matched_signal = signal
                    break
        
        if not feedback_type:
            return None
        
        if not await self._check_rate_limit(user_id):
            logger.info(f"Feedback from {user_id} blocked by rate limit")
            return None
        
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("""
                    INSERT INTO feedback_logs 
                    (user_id, session_id, feedback_type, feedback_signal, 
                     signal_strength, context_topic, previous_ai_response)
                    VALUES (:user_id, :session_id, :feedback_type, :signal,
                            :strength, :topic, :prev_response)
                """), {
                    "user_id": user_id,
                    "session_id": session_id,
                    "feedback_type": feedback_type,
                    "signal": matched_signal,
                    "strength": signal_strength,
                    "topic": context_topic,
                    "prev_response": (previous_ai_response or "")[:500]
                })
                await session.commit()
                
            logger.info(f"Feedback logged: {feedback_type} ({signal_strength}) from {user_id}")
            
            return {
                "type": feedback_type,
                "signal": matched_signal,
                "strength": signal_strength,
                "topic": context_topic
            }
            
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")
            return None
    
    async def _get_anomalous_users(self, days: int = 7) -> set:
        """Identify users with suspicious feedback patterns (>90% same type)."""
        anomalous = set()
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT user_id, feedback_type, COUNT(*) as count
                    FROM feedback_logs
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY user_id, feedback_type
                """))
                rows = result.fetchall()
                
                user_stats = {}
                for row in rows:
                    user_id, fb_type, count = row
                    if user_id not in user_stats:
                        user_stats[user_id] = {"positive": 0, "negative": 0, "total": 0}
                    user_stats[user_id][fb_type] = count
                    user_stats[user_id]["total"] += count
                
                for user_id, stats in user_stats.items():
                    total = stats["total"]
                    if total >= 5:
                        for fb_type in ["positive", "negative"]:
                            ratio = stats[fb_type] / total
                            if ratio >= self.ANOMALY_THRESHOLD:
                                anomalous.add(user_id)
                                logger.warning(f"Anomalous user: {user_id} ({ratio*100:.0f}% {fb_type})")
                                
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
        
        return anomalous
    
    async def _get_trusted_users(self) -> set:
        """Get users who have made purchases (higher trust)."""
        trusted = set()
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT user_id FROM customer_profiles WHERE order_count > 0
                """))
                trusted = {row[0] for row in result.fetchall()}
        except Exception as e:
            logger.warning(f"Trusted user lookup failed: {e}")
        return trusted
    
    async def get_feedback_summary(self, days: int = 7) -> dict:
        """Get aggregated feedback summary for the past N days."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT feedback_type, COUNT(*) as count, COUNT(DISTINCT user_id) as unique_users
                    FROM feedback_logs
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY feedback_type
                """))
                rows = result.fetchall()
                
                summary = {"positive": {"count": 0, "unique_users": 0}, 
                          "negative": {"count": 0, "unique_users": 0}}
                for row in rows:
                    summary[row[0]] = {"count": row[1], "unique_users": row[2]}
                
                return summary
        except Exception as e:
            logger.error(f"Feedback summary failed: {e}")
            return {}
    
    async def get_topic_insights(self, days: int = 30) -> list:
        """Get feedback patterns by topic for learning."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT context_topic, feedback_type, COUNT(*) as count, COUNT(DISTINCT user_id) as unique_users
                    FROM feedback_logs
                    WHERE created_at >= NOW() - INTERVAL '30 days' AND context_topic IS NOT NULL
                    GROUP BY context_topic, feedback_type
                    ORDER BY count DESC LIMIT 20
                """))
                
                return [{"topic": r[0], "type": r[1], "count": r[2], "unique_users": r[3]} 
                        for r in result.fetchall()]
        except Exception as e:
            logger.error(f"Topic insights failed: {e}")
            return []
    
    async def get_user_preference(self, user_id: str) -> dict:
        """Get learned preferences for a specific user."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT preference_data, confidence
                    FROM learned_preferences
                    WHERE preference_type = 'user' AND preference_key = :user_id
                """), {"user_id": user_id})
                row = result.fetchone()
                
                if row:
                    return {"data": row[0], "confidence": row[1]}
                return {}
        except Exception as e:
            logger.error(f"User preference lookup failed: {e}")
            return {}
    
    async def update_learned_preference(
        self,
        preference_type: str,
        preference_key: str,
        preference_data: dict,
        sample_count: int = 1
    ):
        """Update or create a learned preference."""
        try:
            async with AsyncSessionLocal() as session:
                confidence = min(0.9, 0.5 + (sample_count * 0.05))
                
                await session.execute(text("""
                    INSERT INTO learned_preferences 
                    (preference_type, preference_key, preference_data, confidence, sample_count, updated_at)
                    VALUES (:type, :key, :data, :confidence, :count, NOW())
                    ON CONFLICT (preference_type, preference_key) 
                    DO UPDATE SET 
                        preference_data = :data,
                        confidence = :confidence,
                        sample_count = learned_preferences.sample_count + :count,
                        updated_at = NOW()
                """), {
                    "type": preference_type,
                    "key": preference_key,
                    "data": json.dumps(preference_data),
                    "confidence": confidence,
                    "count": sample_count
                })
                await session.commit()
                
            logger.info(f"Updated preference: {preference_type}/{preference_key}")
        except Exception as e:
            logger.error(f"Preference update failed: {e}")
    
    async def run_weekly_learning(self):
        """Aggregate weekly feedback and update learned preferences."""
        logger.info("Running weekly feedback learning aggregation...")
        
        try:
            anomalous_users = await self._get_anomalous_users(days=7)
            trusted_users = await self._get_trusted_users()
            
            if anomalous_users:
                logger.info(f"Excluding {len(anomalous_users)} anomalous users from learning")
            
            topic_insights = await self.get_topic_insights(days=7)
            
            topic_scores = {}
            for insight in topic_insights:
                topic = insight["topic"]
                unique_users = insight.get("unique_users", 1)
                
                if unique_users < self.MIN_UNIQUE_USERS_FOR_UPDATE:
                    continue
                
                if topic not in topic_scores:
                    topic_scores[topic] = {"positive": 0, "negative": 0, "unique_users": 0}
                topic_scores[topic][insight["type"]] = insight["count"]
                topic_scores[topic]["unique_users"] = max(topic_scores[topic]["unique_users"], unique_users)
            
            topics_updated = 0
            for topic, scores in topic_scores.items():
                total = scores["positive"] + scores["negative"]
                unique = scores["unique_users"]
                
                if total < 3 or unique < self.MIN_UNIQUE_USERS_FOR_UPDATE:
                    continue
                    
                satisfaction_ratio = scores["positive"] / total
                preference_data = {
                    "satisfaction_ratio": round(satisfaction_ratio, 2),
                    "needs_improvement": satisfaction_ratio < 0.7,
                    "sample_count": total,
                    "unique_users": unique,
                    "last_updated": datetime.now().isoformat()
                }
                
                await self.update_learned_preference("topic", topic, preference_data, sample_count=total)
                topics_updated += 1
            
            summary = await self.get_feedback_summary(days=7)
            total_positive = summary.get("positive", {}).get("count", 0)
            total_negative = summary.get("negative", {}).get("count", 0)
            unique_positive = summary.get("positive", {}).get("unique_users", 0)
            unique_negative = summary.get("negative", {}).get("unique_users", 0)
            total = total_positive + total_negative
            total_unique = unique_positive + unique_negative
            
            if total > 0 and total_unique >= self.MIN_UNIQUE_USERS_FOR_UPDATE:
                global_prefs = {
                    "overall_satisfaction": round(total_positive / total, 2),
                    "total_feedback": total,
                    "unique_users": total_unique,
                    "anomalous_excluded": len(anomalous_users),
                    "last_updated": datetime.now().isoformat()
                }
                await self.update_learned_preference("global", "default", global_prefs, sample_count=total)
            
            logger.info(f"Weekly learning complete: {topics_updated} topics, {total} feedback, {len(anomalous_users)} excluded")
            return {
                "topics_updated": topics_updated, 
                "total_feedback": total,
                "anomalous_excluded": len(anomalous_users)
            }
            
        except Exception as e:
            logger.error(f"Weekly learning failed: {e}")
            return {"error": str(e)}


# Singleton
feedback_service = FeedbackService()
